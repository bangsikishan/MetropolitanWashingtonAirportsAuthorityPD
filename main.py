import json, os, sys, time

import requests
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException

sys.path.append(os.getcwd())
from utils import (
    check_date,
    create_database_session,
    delete_files_in_directory,
    extract_from_json_and_add_to_db,
    get_env_variables,
    initialize_webdriver,
    insert_to_spiderrecord_database,
    parse_date
)
from function import *

start_time = time.time()

key = 1
script_path = os.path.abspath(__file__)
script_directory = os.path.dirname(script_path)
env_path = os.path.join(script_directory, ".env")
[
    ecgains,
    module_name,
    base_url,
    executable_path,
    download_path,
    server_path,
    json_path,
    browser_type,
    smi_data_url,
    smi_record_url,
    region_name,
    endpoint_url,
    aws_access_key_id,
    aws_secret_access_key
] = get_env_variables(env_path=env_path)

bid_details = {
    "ecgains": ecgains,
    "module_name": module_name,
    "base_url": base_url,
    "download_path": download_path,
    "server_path": server_path
}

driver = initialize_webdriver(
    exec_path=executable_path,
    browser_type=browser_type,
    download_dir=download_path,
    is_headless=True
)

requests.packages.urllib3.disable_warnings()
wait = WebDriverWait(driver, 120)
actions = ActionChains(driver)

driver.get(base_url)

parent_element = wait.until(
    EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/form/div/div[1]/div[4]/div/div/div/div[2]/div/div/div[9]/div/div[3]/div[1]/div/div/div[1]/div/div[5]/div[5]"))
)

no_of_bid_elements = len(parent_element.find_elements(By.XPATH, "./div"))

deployment_key = driver.current_url.split("=")[1]

bid_tab_clicked = False
for index in range(1, no_of_bid_elements + 1):
    bid_data = {}
    bid_element = get_bid_element(driver=driver, index=index)
    
    # DUE DATE
    bid_due_date = bid_element.find_element(By.XPATH, ".//div[5]/span[2]").text
    parsed_due_date = parse_date(bid_due_date.split(",")[0])
    if check_date(date=parsed_due_date):
        continue
    
    # BID NO
    bid_id = bid_element.find_element(By.XPATH, ".//div[1]").text

    # BID TITLE
    bid_title = bid_element.find_element(By.XPATH, ".//div[2]").text

    bid_element.click()

    if not bid_tab_clicked:
        wait.until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/form/div/div[1]/div[4]/div/div/div/div[2]/div/div/div[20]/div[1]/div[1]/div[1]/div[4]/div/div[5]"))
        ).click()
        bid_tab_clicked = True

    table_element = wait.until(
        EC.presence_of_element_located((By.XPATH, "//*[@id='solicitationDocuments$selectorwidgetinline']/div[5]/div/div[3]/table"))
    )

    # RAW JSON DATA CONTAINING LINKS TO DOWNLOAD FILE
    try:
        value_of_element = driver.find_element(By.XPATH, "/html/body/div[1]/form/div/div[1]/div[4]/div/div/div/div[2]/div/div/div[20]/div[1]/div[1]/div[3]/div[5]/div/div/div[13]/div/input").get_attribute("value")
    except NoSuchElementException:
        value_of_element = driver.find_element(By.XPATH, "/html/body/div[1]/form/div/div[1]/div[4]/div/div/div/div[2]/div/div/div[20]/div[1]/div[1]/div[3]/div[4]/div/div/div[13]/div/input").get_attribute("value")
    
    parsed_links = get_urls(json_data=value_of_element)
    download_links = []
    for parsed_link in parsed_links:
        download_links.append(f"https://mwaa.odysseyautomation.com/odyssey/DownloadLog?download.cookie.timestamp={round(time.time() * 1000)}&downloadType=LinkDownload&downloadKey={deployment_key}%7C{parsed_link}%7Cocms.contentdb%7Cocms.website.public_98&downloadMimeType=application%2Fpdf")

    bid_data[index] = {
        "bid_no": bid_id,
        "bid_title": bid_title,
        "bid_due_date": parsed_due_date,
        "files_info": {}
    }

    is_file_size_ok = False
    for idx, download_link in enumerate(download_links, start=1):
        data = download_file(download_path=download_path, file_url=download_link, file_index=idx, ecgain=ecgains, bid_no=bid_id)

        if data is not None:
            bid_data[index]["files_info"].update(data)

    bid_details.update(bid_data)

    # GO BACK
    driver.find_element(By.XPATH, "/html/body/div[1]/form/div/div[1]/div[4]/div/div/div/div[2]/div/div/div[12]/div[1]/a").click()

    # WAIT
    wait.until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/form/div/div[1]/div[4]/div/div/div/div[2]/div/div/div[9]/div/div[3]/div[1]/div/div/div[1]/div/div[5]/div[5]"))
    )
    time.sleep(3)

driver.quit()

with open(os.path.join(json_path, "results.json"), "w") as file:
    json.dump(bid_details, file, indent=4)

spider_record_data = extract_from_json_and_add_to_db(
    path_to_json=os.path.join(json_path, "results.json"),
    db_url=smi_data_url,
    region_name=region_name,
    endpoint_url=endpoint_url,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)

end_time = time.time()
total_execution_time = round((end_time - start_time) / 60)

session = create_database_session(database_url=smi_record_url)
insert_to_spiderrecord_database(session=session, module_name=module_name.split(".")[0], ecgains=ecgains, time_elapsed=total_execution_time,**spider_record_data)

delete_files_in_directory(download_path)
os.remove(os.path.join(json_path, "results.json"))

print("[+] End of script!")