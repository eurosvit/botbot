"""
Simple script to demonstrate scheduler functionality
This would run automatically when deployed with ENABLE_SCHEDULER=true
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app, scheduler
import logging
from threading import Event
import signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scheduler():
    """Test the scheduler functionality"""
    logger.info("🔄 Testing scheduler functionality...")
    
    # Create a flag to stop the test
    stop_event = Event()
    
    def signal_handler(signum, frame):
        logger.info("📛 Received stop signal")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        with app.app_context():
            logger.info("📅 Scheduler is running...")
            logger.info("🕐 Daily reports are scheduled to run at: 8:00 AM (Europe/Kyiv)")
            logger.info("⚙️ To test immediately, you can call the /daily_report endpoint")
            logger.info("🛑 Press Ctrl+C to stop")
            
            # In a real deployment, this would keep the scheduler running
            # For demo purposes, we'll just show that it's configured
            jobs = scheduler.get_jobs()
            if jobs:
                for job in jobs:
                    logger.info(f"📋 Scheduled job: {job.name} - Next run: {job.next_run_time}")
            else:
                logger.warning("⚠️ No scheduled jobs found. Check ENABLE_SCHEDULER environment variable.")
            
            # Wait for stop signal (in real deployment, this runs indefinitely)
            stop_event.wait(timeout=5)  # Wait 5 seconds for demo
            
    except KeyboardInterrupt:
        logger.info("📛 Scheduler test interrupted")
    finally:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("📴 Scheduler stopped")

if __name__ == "__main__":
    test_scheduler()