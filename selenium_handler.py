from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from platform import system
from time import sleep
from random import uniform
from csv_handler import CSVHandler



class SeleniumHandler:
    def __init__(self, job = "Software ngineer", location = "United States"):
        if job == "":
            job = "Software ngineer"
        if location == "":
            location = "United States"

        platfrom = system()

        if platfrom == "Windows":
            self.driver = webdriver.Chrome()
            
        elif platfrom == "Linux":
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options

            options = Options()
            service = Service('/usr/local/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=options)

        else:
            raise PLatfromError("Unsupported platfrom. Please use Windows / Linux")

        self.job = job
        self.location = location
        self.gathered_info = []


    def make_link(self, job, location):
        return f"""https://www.linkedin.com/jobs/search?keywords={
            "%20".join(job.split())
        }&location={
            "%20".join(location.split())
        }"""


    def extract(self):
        self.driver.get(self.make_link(self.job, self.location))
        try:
            wait = WebDriverWait(self.driver, 10)
            job_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.jobs-search__results-list > li")))

            cycle = 0

            for card in job_cards:
                try:
                    if cycle == 0:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", card)
                        WebDriverWait(card, 2).until(lambda s: s.find_element(By.CSS_SELECTOR, "h3.base-search-card__title").text.strip() != "")
                        sleep(uniform(0.05, 0.09))

                    cycle += 1
                    cycle %= 5

                    title = card.find_element(By.CSS_SELECTOR, "h3.base-search-card__title").text
                    company = card.find_element(By.CSS_SELECTOR, "a.hidden-nested-link").text
                    location = card.find_element(By.CSS_SELECTOR, "span.job-search-card__location").text
                    link = card.find_element(By.CSS_SELECTOR, "a.base-card__full-link").get_attribute("href")
                    
                    self.gathered_info.append([title, company, location, link])

                except Exception as e:
                    print("Error extracting data:", e)

            self.driver.quit()
            return True

        except Exception as e:
            print(f"Could not fetch results: {e}")
            self.driver.quit()
            return False


    def save_csv(self, username, name):
        self.db_handler = CSVHandler(self.gathered_info)
        self.db_handler.save(f"saved_csv/{username} {name}.csv")



class PLatfromError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
