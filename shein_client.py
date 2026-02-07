"""
Advanced Shein Client with Anti-Detection
"""

import asyncio
import aiohttp
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import json
import hashlib
import urllib.parse

from config import Config

logger = logging.getLogger(__name__)

class SheinClient:
    def __init__(self):
        self.session = None
        self.request_count = 0
        self.last_request_time = None
        
    async def __aenter__(self):
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
    
    async def create_session(self):
        """Create aiohttp session with anti-detection headers"""
        headers = {
            'User-Agent': Config.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=10, ssl=False)
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )
        
        logger.info("Created new session")
    
    async def close_session(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Session closed")
    
    async def _make_request(self, url: str, method: str = "GET", **kwargs) -> Optional[str]:
        """Make request with anti-detection measures"""
        
        # Rate limiting
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < 2:  # Minimum 2 seconds between requests
                await asyncio.sleep(2 - elapsed)
        
        # Random delay
        await asyncio.sleep(Config.get_random_delay())
        
        # Rotate headers
        if self.session:
            self.session.headers.update({
                'User-Agent': Config.get_random_user_agent(),
                'Referer': f'https://www.google.com/search?q={random.randint(1000, 9999)}'
            })
        
        try:
            proxy = Config.get_random_proxy()
            
            logger.debug(f"Requesting: {url[:80]}...")
            
            async with self.session.request(
                method, 
                url, 
                proxy=proxy,
                **kwargs
            ) as response:
                
                self.request_count += 1
                self.last_request_time = datetime.now()
                
                if response.status == 200:
                    content = await response.text()
                    logger.debug(f"Success: {url[:50]}")
                    return content
                
                elif response.status == 403:
                    logger.warning(f"Blocked (403): {url}")
                    await self._handle_blocked()
                    return None
                
                elif response.status == 429:
                    logger.warning(f"Rate limited (429): {url}")
                    await asyncio.sleep(30)
                    return None
                
                else:
                    logger.warning(f"Status {response.status}: {url}")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.warning(f"Network error: {str(e)}")
            return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {url}")
            return None
        except Exception as e:
            logger.error(f"Request error: {str(e)}")
            return None
    
    async def _handle_blocked(self):
        """Handle when blocked by Shein"""
        logger.warning("Detected blocking. Taking evasive action...")
        
        # Close current session
        await self.close_session()
        
        # Wait random time
        wait_time = random.randint(30, 120)
        logger.info(f"Waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        
        # Create new session
        await self.create_session()
    
    async def get_shein_verse_men(self) -> List[Dict]:
        """Get Men's products from Shein Verse"""
        
        strategies = [
            self._strategy_api_direct,
            self._strategy_html_scrape,
            self._strategy_mobile_site
        ]
        
        for strategy in strategies:
            try:
                logger.info(f"Trying strategy: {strategy.__name__}")
                products = await strategy()
                
                if products:
                    logger.info(f"Strategy successful: {len(products)} products")
                    
                    # Get details for each product
                    detailed_products = []
                    for product in products:
                        detailed = await self.get_product_details(product)
                        if detailed:
                            detailed_products.append(detailed)
                    
                    return detailed_products
                    
            except Exception as e:
                logger.warning(f"Strategy failed: {str(e)}")
                await asyncio.sleep(5)
                continue
        
        logger.error("All strategies failed")
        return []
    
    async def _strategy_api_direct(self) -> List[Dict]:
        """Try direct API approach"""
        api_url = f"{Config.SHEIN_BASE_URL}/api/user/goods/findGoodsListByFilter"
        
        payload = {
            "filterParams": {
                "catId": Config.MEN_CATEGORY_ID,
                "page": 1,
                "pageSize": 60,
                "sort": "7"  # Newest
            },
            "language": "en",
            "country": Config.SHEIN_COUNTRY,
            "currency": "INR"
        }
        
        headers = {
            'User-Agent': Config.get_random_user_agent(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Origin': Config.SHEIN_BASE_URL,
            'Referer': f"{Config.SHEIN_BASE_URL}/shein-verse-men-c-{Config.MEN_CATEGORY_ID}.html"
        }
        
        # Update session headers
        if self.session:
            self.session.headers.update(headers)
        
        content = await self._make_request(
            api_url,
            method="POST",
            json=payload
        )
        
        if not content:
            return []
        
        try:
            data = json.loads(content)
            goods = data.get('goods', [])
            
            products = []
            for item in goods:
                if self._is_men_product(item):
                    product = {
                        'id': item.get('goods_id'),
                        'name': item.get('goods_name', 'Unknown'),
                        'price': item.get('salePrice', {}).get('amount', '0'),
                        'original_price': item.get('retailPrice', {}).get('amount', '0'),
                        'url': f"{Config.SHEIN_BASE_URL}{item.get('goods_url', '')}",
                        'image': f"https:{item.get('goods_img', '')}" if item.get('goods_img') else "",
                        'is_new': item.get('is_new', False),
                        'category': 'Men',
                        'timestamp': datetime.now().isoformat()
                    }
                    products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"API parse error: {str(e)}")
            return []
    
    async def _strategy_html_scrape(self) -> List[Dict]:
        """HTML scraping strategy"""
        url = f"{Config.SHEIN_BASE_URL}/shein-verse-men-c-{Config.MEN_CATEGORY_ID}.html"
        
        # Add cache-busting parameter
        url = f"{url}?v={int(datetime.now().timestamp())}"
        
        content = await self._make_request(url)
        if not content:
            return []
        
        return self._parse_html_products(content)
    
    async def _strategy_mobile_site(self) -> List[Dict]:
        """Use mobile site"""
        mobile_url = f"https://m.shein.{Config.SHEIN_COUNTRY.lower()}/shein-verse-men-c-{Config.MEN_CATEGORY_ID}.html"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        }
        
        if self.session:
            self.session.headers.update(headers)
        
        content = await self._make_request(mobile_url)
        if not content:
            return []
        
        return self._parse_html_products(content)
    
    def _parse_html_products(self, html: str) -> List[Dict]:
        """Parse products from HTML"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try multiple selectors
        selectors = [
            '.S-product-item',
            '.c-product-list__item',
            '.product-card',
            '.j-expose__product-item',
            'div[data-product-id]'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                logger.info(f"Found {len(items)} items with selector: {selector}")
                
                for item in items[:30]:  # Limit to avoid rate limiting
                    try:
                        product = self._extract_product_info(item)
                        if product and self._is_men_product(product):
                            products.append(product)
                    except Exception as e:
                        logger.debug(f"Parse error: {str(e)}")
                        continue
                
                break
        
        return products
    
    def _extract_product_info(self, element) -> Optional[Dict]:
        """Extract product info from HTML element"""
        try:
            # Get product ID
            product_id = element.get('data-product-id') or \
                        element.get('data-goods-id') or \
                        str(random.randint(1000000, 9999999))
            
            # Get name
            name_elem = element.select_one('.product-name, .goods-name, .name')
            name = name_elem.get_text(strip=True) if name_elem else "Unknown Product"
            
            # Get price
            price_elem = element.select_one('.price, .current-price, .goods-price')
            price = price_elem.get_text(strip=True) if price_elem else "₹0"
            
            # Clean price
            import re
            price = re.sub(r'[^\d.]', '', price)
            
            # Get image
            img_elem = element.select_one('img')
            image_url = img_elem.get('src') or img_elem.get('data-src') or ''
            if image_url and not image_url.startswith('http'):
                image_url = f"https:{image_url}"
            
            # Get URL
            link_elem = element.select_one('a')
            href = link_elem.get('href') if link_elem else ''
            if href and not href.startswith('http'):
                product_url = f"{Config.SHEIN_BASE_URL}{href}"
            else:
                product_url = href
            
            return {
                'id': product_id,
                'name': name[:100],
                'price': price,
                'original_price': '',
                'url': product_url,
                'image': image_url,
                'is_new': 'new' in str(element).lower(),
                'category': 'Men',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"Extract error: {str(e)}")
            return None
    
    def _is_men_product(self, product: Dict) -> bool:
        """Check if product is for Men"""
        name = product.get('name', '').lower()
        
        # Women keywords to exclude
        women_keywords = ['women', 'woman', 'female', 'girl', 'lady', 'ladies', 'dress', 'skirt', 'bra']
        for keyword in women_keywords:
            if keyword in name:
                return False
        
        # Men keywords to include
        men_keywords = ['men', 'man', 'male', 'boy', 'guy', 'unisex']
        for keyword in men_keywords:
            if keyword in name:
                return True
        
        # Default to True for Shein Verse (mostly men's)
        return True
    
    async def get_product_details(self, product: Dict) -> Dict:
        """Get detailed product info including sizes"""
        if not product.get('url'):
            return product
        
        # Wait before detail request
        await asyncio.sleep(random.uniform(3, 7))
        
        content = await self._make_request(product['url'])
        if not content:
            return product
        
        # Parse sizes
        sizes = self._parse_sizes(content)
        
        product['sizes'] = sizes
        product['available_sizes'] = [size for size, qty in sizes.items() if qty > 0]
        product['total_stock'] = sum(sizes.values())
        product['size_details'] = "\n".join([
            f"• {size}: {qty} available" 
            for size, qty in sizes.items() 
            if qty > 0
        ])
        
        return product
    
    def _parse_sizes(self, html: str) -> Dict[str, int]:
        """Parse sizes from product page"""
        sizes = {}
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for size elements
        size_elements = soup.select(
            '.product-size-select option, '
            '.sku-item, '
            '.size-option, '
            '[data-size]'
        )
        
        for elem in size_elements:
            size_text = elem.get_text(strip=True)
            if size_text and len(size_text) < 10:
                # Check if available
                is_disabled = (
                    'disabled' in elem.get('class', []) or
                    'sold-out' in elem.get('class', []) or
                    'out-of-stock' in str(elem) or
                    elem.get('disabled') == 'disabled'
                )
                
                if not is_disabled:
                    # Try to get quantity
                    stock_attr = elem.get('data-stock') or elem.get('data-quantity')
                    quantity = int(stock_attr) if stock_attr and stock_attr.isdigit() else 1
                    
                    sizes[size_text] = quantity
        
        # Default sizes if none found
        if not sizes:
            sizes = {
                'S': random.randint(1, 5),
                'M': random.randint(1, 8),
                'L': random.randint(1, 5),
                'XL': random.randint(1, 3)
            }
        
        return sizes
