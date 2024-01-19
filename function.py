import html, json, os, requests, time
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from utils import (
    convert_to_mb,
    find_file,
    generate_md5_hash,
    get_iconverted_value
)

def download_file(download_path: str, file_url: str, file_index: int, ecgain: str, bid_no: str) -> dict:
    data = {}
    is_file_size_ok = False
    while not is_file_size_ok:
        response = requests.get(url=file_url, verify=False)
        file_name = response.headers.get("Content-Disposition").split(";")[1].split("=")[1].strip()

        file_path = os.path.join(download_path, file_name)
        if os.path.exists(file_path):
            time.sleep(3)
            os.remove(file_path)
    
        with open(file_path, "wb") as file:
            file.write(response.content)
    
        if os.path.getsize(file_path) > 0:
            break
    
    iconverted = get_iconverted_value(filename=file_name)
    _, old_file_name, new_file_name = find_file(file_directory=download_path, file_name=file_name)
    file_size_in_mb = convert_to_mb(os.path.getsize(os.path.join(download_path, new_file_name)), "B")
    md5_hash = generate_md5_hash(ecgain=ecgain, bidno=bid_no, filename=old_file_name)

    data[file_index] = {
            "file_name": old_file_name,
            "new_file_name": new_file_name,
            "file_size_in_mb": str(file_size_in_mb) + " MB",
            "file_url": file_url,
            "hash": md5_hash,
            "iconverted": iconverted
    }

    return data

def get_bid_element(driver: webdriver, index: int) -> WebElement:
    return driver.find_element(By.XPATH, f"//*[@id='core_MarketPlace_0']/div[5]/div[{index}]")


def get_urls(json_data: str) -> list:
    parsed_links = []
    translation_table = str.maketrans("", "", "\x01\x02")
    
    original_data = json_data.translate(translation_table)
    original_data = html.unescape(original_data).replace("\\", "/")

    json_data = json.loads(original_data)
    links = json_data["uischema"]["options"]["data"]

    for value in links.values():
        parsed_links.append(quote(value[1].replace("//", "/").replace("/", '\\')))

    return parsed_links

