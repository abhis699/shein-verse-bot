"""
Shein Verse Bot - Anti-Detection Version for Railway
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Import modules
from shein_scraper import SheinScraper
from telegram_bot import TelegramBot
from database import Database

class SheinVerseBot:
    def __init__(self):
        self.scraper = SheinScraper()
        self.telegram = TelegramBot()
        self.db = Database()
        self.is_running = False
        self.check_count = 0
        
    async def start(self):
        """Start the bot"""
        logger.info("🚀 Starting Shein Verse Bot with Anti-Detection...")
        
        # Test Telegram connection
        if not await self.telegram.test_connection():
            logger.error("❌ Telegram connection failed. Check token/chat_id")
            return False
        
        # Send startup message
        await self.telegram.send_startup_message()
        
        # Initial scan
        logger.info("🔍 Performing initial scan...")
        await self.scan_products()
        
        self.is_running = True
        logger.info("✅ Bot started successfully")
        return True
    
    async def scan_products(self):
        """Scan for new products with anti-detection"""
        try:
            # Get current products with anti-detection
            products = await self.scraper.get_men_products()
            
            if not products:
                logger.warning("⚠️ No products found")
                return
            
            logger.info(f"📊 Found {len(products)} Men's products")
            
            new_alerts = 0
            for product in products:
                # Check if product is new or restocked
                is_new, is_restock = await self.db.check_product(product)
                
                if is_new or is_restock:
                    # Get detailed info with sizes
                    detailed_product = await self.scraper.get_product_details(product)
                    
                    # Send alert
                    await self.telegram.send_product_alert(detailed_product, is_new, is_restock)
                    
                    # Save to database
                    await self.db.save_product(detailed_product, is_new, is_restock)
                    
                    new_alerts += 1
                    
                    # Anti-detection delay between alerts
                    await asyncio.sleep(2)
            
            self.check_count += 1
            
            # Send summary every 10 checks (approx 30-40 minutes)
            if self.check_count % 10 == 0:
                await self.send_summary()
            
            logger.info(f"✅ Scan complete. Sent {new_alerts} alerts")
            
        except Exception as e:
            logger.error(f"❌ Scan error: {str(e)}")
    
    async def send_summary(self):
        """Send periodic summary"""
        stats = await self.db.get_stats()
        
        summary = f"""
📊 **SHEIN VERSE SUMMARY** 
🕒 {datetime.now().strftime('%H:%M:%S')}

📦 **Products Tracked:** {stats['total_products']}
🆕 **New Today:** {stats['new_today']}
🔄 **Restocks Today:** {stats['restocks_today']}
🔍 **Total Scans:** {self.check_count}

✅ **Bot Status:** Running normally
🛡️ **Anti-Detection:** Active
        """
        
        await self.telegram.send_message(summary)
    
    async def run(self):
        """Main loop"""
        while self.is_running:
            try:
                await self.scan_products()
                
                # Random interval to avoid patterns
                interval = self.scraper.get_random_interval()
                logger.info(f"⏳ Next check in {interval} seconds...")
                await asyncio.sleep(interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {str(e)}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop the bot gracefully"""
        self.is_running = False
        await self.telegram.send_message("🛑 Bot stopped gracefully")
        logger.info("👋 Bot stopped")

# Health check endpoint for Railway
from aiohttp import web

async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_server():
    """Start health check server"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', '8080')))
    await site.start()
    logger.info(f"🌐 Health check server running on port {os.getenv('PORT', '8080')}")

async def main():
    """Main function"""
    # Start health check server
    server_task = asyncio.create_task(start_server())
    
    # Start bot
    bot = SheinVerseBot()
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start bot
    if await bot.start():
        await bot.run()
    
    # Cleanup
    await bot.stop()

if __name__ == "__main__":
    # Check environment variables
    required_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        logger.info("💡 Set them on Railway dashboard or in .env file")
        sys.exit(1)
    
    # Run bot
    asyncio.run(main())
