import asyncio
from pyppeteer import launch
import time

async def test_dashboard():
    """Test the dashboard with Puppeteer to troubleshoot the 'Connecting to server...' issue"""

    logger.info("Launching browser...")
    browser = await launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
    page = await browser.newPage()

    # Set up console logging
    page.on('console', lambda msg: logger.info(f'PAGE LOG: {msg.text}'))

    # Navigate to the leaderboard page
    logger.info("Navigating to http://127.0.0.1:5000/leaderboard...")
    await page.goto('http://127.0.0.1:5000/leaderboard', {'waitUntil': 'networkidle0'})

    # Wait for page to load
    await page.waitForSelector('#leaderboard-table', {'timeout': 10000})

    # Check the content of the leaderboard table
    leaderboard_content = await page.evaluate('''
        () => {
            const table = document.getElementById('leaderboard-table');
            return table ? table.innerHTML : 'Table not found';
        }
    ''')

    logger.info("Leaderboard table content:")
    logger.info(leaderboard_content[:500] + "..." if len(leaderboard_content) > 500 else leaderboard_content)

    # Check connection status
    connection_status = await page.evaluate('''
        () => {
            const statusEl = document.getElementById('connection-status');
            return statusEl ? statusEl.innerHTML : 'Status element not found';
        }
    ''')

    logger.info(f"Connection status: {connection_status}")

    # Check if Socket.IO is loaded
    socket_loaded = await page.evaluate('''
        () => {
            return typeof io !== 'undefined';
        }
    ''')

    logger.info(f"Socket.IO loaded: {socket_loaded}")

    # Wait a bit to see if data loads
    logger.info("Waiting 10 seconds for data to load...")
    await asyncio.sleep(10)

    # Check again after waiting
    leaderboard_content_after = await page.evaluate('''
        () => {
            const table = document.getElementById('leaderboard-table');
            return table ? table.innerHTML : 'Table not found';
        }
    ''')

    logger.info("Leaderboard table content after waiting:")
    logger.info(leaderboard_content_after[:500] + "..." if len(leaderboard_content_after) > 500 else leaderboard_content_after)

    # Check for any error messages in the page
    errors = await page.evaluate('''
        () => {
            const elements = document.querySelectorAll('.text-muted');
            let errorTexts = [];
            elements.forEach(el => {
                if (el.textContent.includes('No') || el.textContent.includes('available')) {
                    errorTexts.push(el.textContent.trim());
                }
            });
            return errorTexts;
        }
    ''')

    logger.info(f"Error messages found: {errors}")

    # Check browser console for errors
    console_messages = []
    def log_console(msg):
        console_messages.append(f"{msg.type}: {msg.text}")

    page.on('console', log_console)

    await browser.close()

    logger.info("Test completed.")

if __name__ == '__main__':
    asyncio.run(test_dashboard())