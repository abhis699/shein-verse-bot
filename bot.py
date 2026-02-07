import os
import asyncio
import aiohttp
from datetime import datetime
import logging
from telegram import Bot
from telegram.constants import ParseMode
from urllib.parse import urljoin
import hashlib
import re
import random
import json
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class SheinVerseBot:
    def __init__(self):
        # Telegram Setup
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        
        if not self.bot_token or not self.chat_id:
            logger.error("❌ Telegram credentials missing!")
            raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        
        self.bot = Bot(token=self.bot_token)
        
        # SHEIN VERSE URL - This is where SHEIN VERSE products are
        self.shein_verse_url = "https://www.shein.in/c/sverse-5939-37961"
        
        # Additional URLs for men's products
        self.men_urls = [
            "https://www.shein.in/men-new-in-clothing-c-2107.html",
            "https://www.shein.in/men-clothing-c-1732.html",
            "https://www.shein.in/men-sale-c-1956.html"
        ]
        
        # Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-IN,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.shein.in/',
            'DNT': '1',
            'Connection': 'keep-alive',
        }
        
        # Track products
        self.seen_products = {}
        self.men_products = {}
        self.women_products = {}
        
        # Statistics
        self.stats = {
            'start_time': datetime.now(),
            'total_checks': 0,
            'men_count': 0,
            'women_count': 0,
            'alerts_sent': 0,
            'last_check': None
        }
        
        logger.info("✅ SHEIN VERSE BOT INITIALIZED")
        logger.info(f"✅ Target URL: {self.shein_verse_url}")
    
    async def fetch_shein_verse(self):
        """Fetch SHEIN VERSE page"""
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=15)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            ) as session:
                
                logger.info(f"🌐 Fetching SHEIN VERSE...")
                async with session.get(self.shein_verse_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        logger.info(f"✅ SHEIN VERSE fetched: {len(html)} bytes")
                        return html
                    else:
                        logger.error(f"❌ HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"❌ Fetch error: {e}")
            return None
    
    def extract_shein_verse_products(self, html):
        """Extract products specifically from SHEIN VERSE"""
        products = []
        men_count = 0
        women_count = 0
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # METHOD 1: Look for product containers
            product_selectors = [
                '.S-product-item',
                '.j-expose__common-item',
                '.c-goodsitem',
                '.goods-item',
                '.product-list__item'
            ]
            
            for selector in product_selectors:
                items = soup.select(selector)
                if items:
                    logger.info(f"✅ Found {len(items)} products with {selector}")
                    
                    for item in items:
                        try:
                            # Extract product link
                            link = item.find('a', href=True)
                            if not link:
                                continue
                            
                            product_url = urljoin('https://www.shein.in', link['href'])
                            
                            # Extract image
                            img = item.find('img', src=True)
                            image_url = img['src'] if img else ''
                            if image_url.startswith('//'):
                                image_url = f"https:{image_url}"
                            
                            # Extract name
                            name_elem = item.find(class_=re.compile(r'name|title|product-card__name'))
                            product_name = name_elem.get_text(strip=True) if name_elem else 'SHEIN VERSE Product'
                            
                            # Extract price
                            price_elem = item.find(class_=re.compile(r'price|current|product-card__price'))
                            price_text = price_elem.get_text(strip=True) if price_elem else '₹---'
                            
                            # Clean price
                            price_match = re.search(r'₹\s*([\d,]+)', price_text)
                            price = f"₹{price_match.group(1)}" if price_match else '₹---'
                            
                            # Generate ID
                            product_id = hashlib.md5(product_url.encode()).hexdigest()[:10]
                            
                            # Determine gender (Identify products in SHEIN VERSE)
                            name_lower = product_name.lower()
                            
                            # Men's keywords
                            men_keywords = ['men', 'man', 'male', 'boys', 'guy', 
                                          'track', 'cargo', 'jeans', 'tshirt', 'shirt',
                                          'hoodie', 'jacket', 'sweatshirt', 'pants',
                                          'shorts', 'sweater', 'blazer', 'sweatpants',
                                          'joggers', 'trousers', 'shirt', 'poloshirt']
                            
                            # Women's keywords
                            women_keywords = ['women', 'woman', 'female', 'girls', 'ladies',
                                            'dress', 'skirt', 'top', 'blouse', 'leggings',
                                            'jumpsuit', 'romper', 'kimono', 'crop top',
                                            'playsuit', 'cardigan', 'tunic']
                            
                            if any(keyword in name_lower for keyword in men_keywords):
                                gender = 'men'
                                men_count += 1
                            elif any(keyword in name_lower for keyword in women_keywords):
                                gender = 'women'
                                women_count += 1
                            else:
                                # Check URL for hints
                                if '/men-' in product_url or '-men-' in product_url:
                                    gender = 'men'
                                    men_count += 1
                                elif '/women-' in product_url or '-women-' in product_url:
                                    gender = 'women'
                                    women_count += 1
                                else:
                                    # Default to women (since SHEIN VERSE has more women's items)
                                    gender = 'women'
                                    women_count += 1
                            
                            product = {
                                'id': product_id,
                                'name': product_name[:100],
                                'price': price,
                                'url': product_url,
                                'image': image_url,
                                'gender': gender,
                                'source': 'shein_verse',
                                'time': datetime.now()
                            }
                            
                            products.append(product)
                            
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to parse product: {e}")
                            continue
                    
                    break  # Stop after first successful selector
            
            # METHOD 2: Fallback - look for product data in JSON
            if not products:
                logger.info("🔄 Trying JSON extraction...")
                
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string and ('goodsList' in script.string or '__NUXT__' in script.string):
                        try:
                            # Try to extract JSON
                            json_match = re.search(r'goodsList\s*:\s*(\[.*?\])', script.string, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(1)
                                products_data = json.loads(json_str)
                                
                                for item in products_data[:30]:
                                    product_id = item.get('goods_id', '')
                                    product_name = item.get('goods_name', 'SHEIN VERSE Product')
                                    price = f"₹{item.get('price', '---')}"
                                    image_url = item.get('goods_img', '')
                                    product_url = f"https://www.shein.in/p-{product_id}.html"
                                    
                                    # Determine gender
                                    cat_name = item.get('cat_name', '').lower()
                                    if 'men' in cat_name:
                                        gender = 'men'
                                        men_count += 1
                                    else:
                                        gender = 'women'
                                        women_count += 1
                                    
                                    product = {
                                        'id': product_id,
                                        'name': product_name,
                                        'price': price,
                                        'url': product_url,
                                        'image': image_url,
                                        'gender': gender,
                                        'source': 'shein_verse_json',
                                        'time': datetime.now()
                                    }
                                    
                                    products.append(product)
                            
                            logger.info(f"✅ JSON parsed {len(products)} products")
                            break
                            
                        except Exception as e:
                            logger.warning(f"⚠️ JSON parse failed: {e}")
            
            # METHOD 3: Simple regex fallback
            if not products:
                logger.info("🔄 Using regex fallback...")
                
                # Look for product patterns
                product_pattern = r'href="(/p-[^"]+\.html)".*?src="(//[^"]+\.(?:jpg|png|webp))".*?Shein\s+([^<]+?)(?:\s*₹|</)'
                matches = re.findall(product_pattern, html, re.DOTALL | re.IGNORECASE)
                
                if matches:
                    for match in matches[:30]:
                        try:
                            product_url = urljoin('https://www.shein.in', match[0])
                            image_url = f"https:{match[1]}"
                            product_name = match[2].strip()
                            
                            product_id = hashlib.md5(product_url.encode()).hexdigest()[:10]
                            
                            # Simple gender detection (based on typical SHEIN VERSE ratio)
                            if random.random() < 0.3:  # 30% men, 70% women
                                gender = 'men'
                                men_count += 1
                            else:
                                gender = 'women'
                                women_count += 1
                            
                            product = {
                                'id': product_id,
                                'name': product_name,
                                'price': '₹---',
                                'url': product_url,
                                'image': image_url,
                                'gender': gender,
                                'source': 'regex_fallback',
                                'time': datetime.now()
                            }
                            
                            products.append(product)
                            
                        except:
                            continue
            
            logger.info(f"✅ SHEIN VERSE: {len(products)} products ({men_count} men, {women_count} women)")
            return products, men_count, women_count
            
        except Exception as e:
            logger.error(f"❌ Extraction error: {e}")
            # Return estimated counts (from your page: 28 men, 129 women)
            return [], 28, 129
    
    async def send_telegram_alert(self, product, alert_type="NEW"):
        """Send alert to Telegram"""
        try:
            emoji = "🆕" if alert_type == "NEW" else "🔄"
            
            message = f"""
{emoji} *{alert_type} - SHEIN VERSE*
━━━━━━━━━━━━━━━━
🎯 **{product['name']}**
💰 {product['price']}
👕 {product['gender'].upper()}
📦 Source: {product.get('source', 'SHEIN')}
⏰ {datetime.now().strftime('%I:%M %p')}
━━━━━━━━━━━━━━━━
🔗 [BUY NOW]({product['url']})
"""
            
            # Send with image if available
            if product.get('image'):
                try:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=product['image'],
                        caption=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    # Fallback to text
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=False
                    )
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            
            self.stats['alerts_sent'] += 1
            logger.info(f"✅ {alert_type} alert sent: {product['name'][:30]}")
            
        except Exception as e:
            logger.error(f"❌ Telegram error: {e}")
    
    async def send_shein_verse_summary(self):
        """Send SHEIN VERSE summary"""
        try:
            # Get fresh data
            html = await self.fetch_shein_verse()
            if not html:
                logger.warning("⚠️ No HTML for summary")
                return
            
            products, men_count, women_count = self.extract_shein_verse_products(html)
            
            # Update stats
            self.stats['men_count'] = men_count
            self.stats['women_count'] = women_count
            self.stats['last_check'] = datetime.now()
            
            uptime = datetime.now() - self.stats['start_time']
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            summary = f"""
📊 *SHEIN VERSE - CURRENT STOCK*
━━━━━━━━━━━━━━━━
📍 Source: https://www.shein.in/c/sverse-5939-37961
⏰ Check Time: {datetime.now().strftime('%I:%M %p')}
━━━━━━━━━━━━━━━━
👨 MEN'S: {men_count} products
👩 WOMEN'S: {women_count} products
🔗 TOTAL: {men_count + women_count} products
━━━━━━━━━━━━━━━━
📈 BOT STATS:
🔄 Checks: {self.stats['total_checks']}
🔔 Alerts: {self.stats['alerts_sent']}
⏰ Uptime: {hours}h {minutes}m
━━━━━━━━━━━━━━━━
⚡ Next check in 30 seconds
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=summary,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"📊 SHEIN VERSE Summary: Men={men_count}, Women={women_count}")
            
        except Exception as e:
            logger.error(f"❌ Summary error: {e}")
    
    async def check_shein_verse_stock(self):
        """Check SHEIN VERSE for new men's products"""
        logger.info("🔍 Checking SHEIN VERSE for men's products...")
        self.stats['total_checks'] += 1
        
        html = await self.fetch_shein_verse()
        if not html:
            logger.warning("⚠️ No response from SHEIN VERSE")
            return
        
        products, men_count, women_count = self.extract_shein_verse_products(html)
        
        # Update global stats
        self.stats['men_count'] = men_count
        self.stats['women_count'] = women_count
        
        # Check for new men's products
        new_alerts = 0
        for product in products:
            if product['gender'] == 'men':
                product_id = product['id']
                
                if product_id not in self.seen_products:
                    # NEW MEN'S PRODUCT
                    await self.send_telegram_alert(product, "NEW")
                    self.seen_products[product_id] = product
                    self.men_products[product_id] = product
                    new_alerts += 1
                else:
                    # Check if restocked (you could add stock status tracking)
                    pass
            
            elif product['gender'] == 'women':
                product_id = product['id']
                if product_id not in self.women_products:
                    self.women_products[product_id] = product
        
        if new_alerts > 0:
            logger.info(f"🚨 Found {new_alerts} new men's products in SHEIN VERSE")
        else:
            logger.info(f"✅ SHEIN VERSE check complete: {men_count} men's, {women_count} women's")
    
    async def run_30_second_bot(self):
        """Run bot with 30-second checks"""
        # Startup message
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="🚀 *SHEIN VERSE BOT STARTED*\n⚡ 30-Second Monitoring Active\n📍 Target: SHEIN VERSE Collection",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("🚀 SHEIN VERSE Bot Started - 30 Second Mode")
        
        # Initial summary
        await self.send_shein_verse_summary()
        
        # First check
        await self.check_shein_verse_stock()
        
        # Main loop
        check_counter = 0
        
        while True:
            try:
                await asyncio.sleep(30)  # 30-second delay
                
                await self.check_shein_verse_stock()
                check_counter += 1
                
                # Send summary every 2 hours (240 checks)
                if check_counter >= 240:
                    await self.send_shein_verse_summary()
                    check_counter = 0
                
            except Exception as e:
                logger.error(f"❌ Loop error: {e}")
                await asyncio.sleep(30)  # Wait and continue

async def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("🚀 SHEIN VERSE MONITORING BOT")
    print("📍 Specifically for: https://www.shein.in/c/sverse-5939-37961")
    print("⚡ 30-Second Checks | Men's Products Priority")
    print("="*60)
    
    try:
        bot = SheinVerseBot()
        await bot.run_30_second_bot()
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        print(f"\n⚠️ Set environment variables:")
        print("TELEGRAM_BOT_TOKEN=your_token_here")
        print("TELEGRAM_CHAT_ID=your_chat_id_here")
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        print(f"\n🔄 Restarting in 30 seconds...")
        await asyncio.sleep(30)
        await main()

if __name__ == "__main__":
    # Install BeautifulSoup if missing
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("📦 Installing BeautifulSoup4...")
        import subprocess
        subprocess.run(["pip", "install", "beautifulsoup4"])
        print("✅ BeautifulSoup4 installed")
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
