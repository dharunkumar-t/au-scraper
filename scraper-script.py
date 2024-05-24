import os
import sys
import time
import logging
import argparse
import numpy as np
from PIL import Image
import urllib.request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CaptchaSolver:
    def __init__(self):
        self.test_set = self._load_test_set()
        self.char_map = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        
    def _load_test_set(self):
        """
        Load character templates for pattern matching.
        Each template is a 10x8 binary matrix representing a character.
        """
        templates = []
        
        template_0 = np.array([
            [0, 1, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 0, 0, 0, 0, 1, 1],
            [1, 1, 0, 0, 0, 0, 1, 1],
            [1, 1, 0, 0, 0, 0, 1, 1],
            [1, 1, 0, 0, 0, 0, 1, 1],
            [1, 1, 0, 0, 0, 0, 1, 1],
            [1, 1, 0, 0, 0, 0, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 0]
        ], dtype=np.uint8) * 255
        
        templates.append(template_0)
        
        return templates
        
    def _preprocess_image(self, image_path):
        """Convert captcha image to binary matrix"""
        try:
            img = Image.open(image_path).convert('L')
            img = img.resize((70, 20))
            matrix = np.array(img)

            matrix = (matrix > 128) * 255
            return matrix
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            raise
        
    def _extract_character(self, matrix, position):
        """Extract single character matrix (10x8) from position"""
        try:
            start_x = position * 10
            char_matrix = matrix[:, start_x:start_x + 10]
            return char_matrix
        except Exception as e:
            logger.error(f"Error extracting character at position {position}: {e}")
            raise
        
    def _calculate_match_percentage(self, char_matrix, test_matrix):
        """Calculate percentage match between character and test matrices"""
        try:
            matching_pixels = np.sum(char_matrix == test_matrix)
            total_pixels = char_matrix.size
            return (matching_pixels / total_pixels) * 100
        except Exception as e:
            logger.error(f"Error calculating match percentage: {e}")
            raise
        
    def solve(self, captcha_path):
        """Solve the captcha and return the result string"""
        try:
            matrix = self._preprocess_image(captcha_path)
            result = []
            
            for i in range(6):
                char_matrix = self._extract_character(matrix, i)
                best_match = 0
                best_char = ''
                
                for idx, test_matrix in enumerate(self.test_set):
                    match_percent = self._calculate_match_percentage(char_matrix, test_matrix)
                    if match_percent > best_match:
                        best_match = match_percent
                        best_char = self.char_map[idx]
                
                if best_match < 50:
                    logger.warning(f"Low confidence match for character at position {i}")
                
                result.append(best_char)
            
            return ''.join(result)
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            raise

class AUInfoExtractor:
    def __init__(self):
        self.captcha_solver = CaptchaSolver()
        self.base_url = "https://coe.annauniv.edu"
        self.login_url = f"{self.base_url}/login.php"
        self.marks_url = f"{self.base_url}/student/marks.php"
        
    def setup_driver(self):
        """Setup Chrome WebDriver with appropriate options"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {e}")
            raise
        
    def login(self, driver, username, password, max_retries=3):
        """Handle login process including captcha solving"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Login attempt {attempt + 1}/{max_retries}")
                driver.get(self.login_url)
                
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                
                captcha_elem = driver.find_element(By.ID, "captchaImage")
                captcha_path = f"temp_captcha_{attempt}.png"
                captcha_elem.screenshot(captcha_path)
                
                captcha_solution = self.captcha_solver.solve(captcha_path)
                logger.info(f"Captcha solution: {captcha_solution}")
            
            
                driver.find_element(By.NAME, "username").send_keys(username)
                driver.find_element(By.NAME, "password").send_keys(password)
                driver.find_element(By.NAME, "captcha").send_keys(captcha_solution)
                
                driver.find_element(By.NAME, "login").click()
                

                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "dashboard"))
                )
                
                logger.info("Login successful")
                return True
                
            except TimeoutException:
                logger.warning(f"Login attempt {attempt + 1} failed (timeout)")
                if attempt == max_retries - 1:
                    raise
                continue
                
            except Exception as e:
                logger.error(f"Login attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                continue
                
            finally:
                if os.path.exists(captcha_path):
                    os.remove(captcha_path)
        
        return False
    
    def extract_marks(self, driver, semester=None):
        """Extract marks information"""
        try:
            driver.get(self.marks_url)
            
            if semester:
            
                semester_select = driver.find_element(By.NAME, "semester")
                semester_select.click()
                semester_option = driver.find_element(By.XPATH, f"//option[text()='{semester}']")
                semester_option.click()
            
           
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "marks-table"))
            )
            
           
            marks_table = driver.find_element(By.CLASS_NAME, "marks-table")
            rows = marks_table.find_elements(By.TAG_NAME, "tr")
            
            marks_data = []
            for row in rows[1:]:  
                cols = row.find_elements(By.TAG_NAME, "td")
                subject_data = {
                    "code": cols[0].text,
                    "name": cols[1].text,
                    "internal": cols[2].text,
                    "external": cols[3].text,
                    "total": cols[4].text,
                    "result": cols[5].text
                }
                marks_data.append(subject_data)
            
            return marks_data
            
        except Exception as e:
            logger.error(f"Error extracting marks: {e}")
            raise
    
    def extract_info(self, username, password, semester=None):
        """Main method to extract student information"""
        driver = None
        try:
            driver = self.setup_driver()
            
            if not self.login(driver, username, password):
                raise Exception("Failed to login after maximum retries")
            
            marks_data = self.extract_marks(driver, semester)
            return marks_data
            
        except Exception as e:
            logger.error(f"Error in information extraction: {e}")
            raise
            
        finally:
            if driver:
                driver.quit()

def main():
    parser = argparse.ArgumentParser(description='AU Student Information Extraction Tool')
    parser.add_argument('--username', required=True, help='Your login username')
    parser.add_argument('--password', required=True, help='Your login password')
    parser.add_argument('--semester', help='Specific semester to fetch marks for')
    parser.add_argument('--output', help='Output file path for marks data')
    
    args = parser.parse_args()
    
    try:
        extractor = AUInfoExtractor()
        marks_data = extractor.extract_info(args.username, args.password, args.semester)
        
        if marks_data:
            if args.output:
                
                import json
                with open(args.output, 'w') as f:
                    json.dump(marks_data, f, indent=2)
                logger.info(f"Marks data saved to {args.output}")
            else:
              
                for subject in marks_data:
                    print(f"\nSubject: {subject['name']} ({subject['code']})")
                    print(f"Internal: {subject['internal']}")
                    print(f"External: {subject['external']}")
                    print(f"Total: {subject['total']}")
                    print(f"Result: {subject['result']}")
                    
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()