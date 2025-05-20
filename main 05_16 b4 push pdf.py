import requests
import io
import pdfplumber
from openai import OpenAI
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pydantic import BaseModel
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import time
import os
from typing import List, Dict, Optional
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime
from selenium.common.exceptions import ElementClickInterceptedException
import tempfile
from zoneinfo import ZoneInfo
import json
import base64
from dotenv import load_dotenv
import shutil
import re
from gs import fill_GS_form
from lv import fill_LV_form

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROK2_API_KEY = os.getenv("GROK2_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment flag
IsProduction = True    #Use web drivr

UseGrok = False

# Initialize FastAPI app
app = FastAPI()
executor = ThreadPoolExecutor(max_workers=8)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Pydantic models
class LoginRequest(BaseModel):
    session_id: str
    url: str
    username: str
    password: str

class CalculationData(BaseModel):
    processedData: List[Dict]
    inputs: Dict
    totalAccumulatedMP: float

class CashValueInfo(BaseModel):
    age_1: int
    age_2: int
    age_1_cash_value: int
    age_2_cash_value: int
    annual_premium: int

class FormData(BaseModel):
    isCorporateCustomer: bool
    isPolicyHolder: bool
    surname: str
    givenName: str
    chineseName: str
    insuranceAge: str
    gender: str
    isSmoker: bool
    basicPlan: str
    currency: str
    notionalAmount: str
    premiumPaymentPeriod: str 
    premiumPaymentMethod: str
    useInflation: bool
    proposalLanguage: str
    selectedAge1: int
    selectedAge2: int

class OtpRequest(BaseModel):
    session_id: str
    otp: str
    calculation_data: CalculationData
    cashValueInfo: CashValueInfo
    formData: FormData

class RetryRequest(BaseModel):
    session_id: str
    new_notional_amount: str

# Global storage
sessions = {}  # session_id -> {"driver": driver, "form_data": form_data}
session_queues = {}  # session_id -> asyncio.Queue
TIMEOUT = 120

# Helper function to run synchronous tasks in a thread
async def run_in_thread(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args)

# Helper function to log messages and put into queue
def log_message(message: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    if IsProduction:
        logger.info(message)
    else:
        print(message)
    asyncio.run_coroutine_threadsafe(queue.put(message), loop)

# Selenium worker for initial login
def selenium_worker(session_id: str, url: str, username: str, password: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-gpu")
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        prefs = {
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
        }
        options.add_experimental_option("prefs", prefs)

        if IsProduction:
            options.add_argument('--headless')
            driver = webdriver.Remote(command_executor='https://standalone-chrome-production-57ca.up.railway.app', options=options)
        else:
            driver = webdriver.Chrome(options=options)

        driver.get(url)

        login_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.ID, "user"))
        )
        login_field.send_keys(username)
        log_message("使用者名稱已發送", queue, loop)

        driver.find_element(By.ID, 'password').send_keys(password)
        log_message("密碼已發送", queue, loop)

        driver.find_element(By.XPATH, '//*[@id="form"]/button').click()
        log_message("點擊登入按鈕", queue, loop)

        mailOption = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, "//label[contains(., '已登記的電郵地址')]"))
        )
        mailOption.click()
        log_message("點選郵件選項", queue, loop)

        sendOtpRequestButton = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="otp"]/div[2]/button[1]'))
        )
        sendOtpRequestButton.click()
        log_message("一次性密碼從電郵發放中...", queue, loop)

        sessions[session_id] = {"driver": driver}
    except Exception as e:
        log_message(f"Selenium error: {str(e)}", queue, loop)
        if session_id in sessions:
            driver = sessions.pop(session_id).get("driver")
            if driver:
                driver.quit()
        raise

# Helper function to perform checkout and capture PDF from network
def perform_checkout(driver, notional_amount: str, form_data: Dict, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, calculation_data: Dict, cash_value_info: Dict, session_id: str):
    try:
        policy_field = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/qq-left-tab/div/button[7]/span[2]/div'))
        )
        policy_field.click()
        log_message("保費摘要 已點選, 請稍後...", queue, loop)

        class EitherElementLocated:
            def __init__(self, locator1, locator2):
                self.locator1 = locator1
                self.locator2 = locator2

            def __call__(self, driver):
                system_messages = driver.find_elements(*self.locator1)
                for msg in system_messages:
                    if msg.is_displayed() and any(keyword in msg.text for keyword in ["所達年齡", "總每年保費不能少於"]):
                        return {"type": "system_message", "element": msg}
                try:
                    view_element = driver.find_element(*self.locator2)
                    if view_element.is_displayed():
                        return {"type": "view_button", "element": view_element}
                except NoSuchElementException:
                    pass
                return False

        system_message_locator = (By.XPATH, "//div[@class='control-message']//li")
        view_button_locator = (By.XPATH, "/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/div/div/qq-premium-summary/div/div[3]/button/span[2]")

        result = WebDriverWait(driver, 30).until(
            EitherElementLocated(system_message_locator, view_button_locator)
        )
        basicPlan_ = str(form_data['basicPlan'])
        if result["type"] == "system_message":
            system_message = result["element"].text
            log_message(f"系統信息: {system_message}", queue, loop)
            cleaned_amount = notional_amount.replace(',', '')
            integer_part = cleaned_amount.split('.')[0]
            formatted_amount = f"{int(integer_part):,}"
            return {
                "status": "retry",
                "system_message": f"{system_message}\n 對上一次輸入的名義金額為${formatted_amount}"
            }
        elif result["type"] == "view_button":
            view_button = result["element"]
            view_button.click()
            log_message("名義金額而獲通過", queue, loop)
            log_message("檢視建議書 已點選", queue, loop)

            save_input_field = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@matinput and @maxlength='80']"))
            )
            tz_gmt8 = ZoneInfo("Asia/Shanghai")
            timestamp = datetime.now(tz_gmt8).strftime("%Y%m%d%H%M")
            filename = f"{basicPlan_}_{timestamp}"
            save_input_field.clear()
            save_input_field.send_keys(filename)

            save_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//mat-dialog-container//div[@class='dialog-buttons']/button[contains(., '儲存')]"))
            )
            try:
                save_button.click()
                log_message("儲存 按鍵 已成功點選", queue, loop)
            except:
                ActionChains(driver).move_to_element(save_button).pause(0.5).click().perform()
                log_message("儲存2 已成功點選", queue, loop)

            if str(form_data['proposalLanguage']) == "zh":
                proposal_language_radio = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@value='zh']/ancestor::div[contains(@class, 'mdc-radio')]"))
                )
                proposal_language_radio.click()
                log_message(f"建議書語言選擇按鈕 = {str(form_data['proposalLanguage'])}", queue, loop)
            elif str(form_data['proposalLanguage']) == "sc":
                proposal_language_radio = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@value='sc']/ancestor::div[contains(@class, 'mdc-radio')]"))
                )
                proposal_language_radio.click()
                log_message(f"建議書語言選擇按鈕 = {str(form_data['proposalLanguage'])}", queue, loop)
            else:
                proposal_language_radio = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@value='zh']/ancestor::div[contains(@class, 'mdc-radio')]"))
                )
                proposal_language_radio.click()
                log_message(f"建議書語言選擇按鈕 = {str(form_data['proposalLanguage'])}", queue, loop)

            label = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//label[.//div[text()='所有年期']]"))
            )
            label.click()
            log_message("所有年期 已成功點選", queue, loop)

            print_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//cpos-button[.//span[contains(., '列印建議書')]]//button[contains(@class, 'agent-btn')]"))
            )
            try:
                print_button.click()
                log_message("列印建議書 按鍵 已成功點選", queue, loop)
            except:
                ActionChains(driver).move_to_element_with_offset(print_button, 5, 5).pause(0.3).click().perform()
                log_message("列印建議書2 按鍵 已成功點選", queue, loop)
            
            log_message("列印中, 請稍後..." , queue, loop)
            
            # Wait for PDF response
            pdf_request_id = None
            pdf_content = None
            start_time = time.time()
            polling_interval = 0.5  # seconds

            while time.time() - start_time < 60:
                logs = driver.get_log('performance')
                for log in logs:
                    message = json.loads(log['message'])['message']
                    if message['method'] == 'Network.responseReceived':
                        response = message['params']['response']
                        if response['mimeType'] == 'application/pdf':
                            pdf_request_id = message['params']['requestId']
                    elif message['method'] == 'Network.loadingFinished' and pdf_request_id is not None:
                        if message['params']['requestId'] == pdf_request_id:
                            try:
                                body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': pdf_request_id})
                                if body['base64Encoded']:
                                    pdf_content = base64.b64decode(body['body'])
                                else:
                                    pdf_content = body['body'].encode()
                                break
                            except:
                                pass  # Continue waiting if getting the body fails
                if pdf_content:
                    break
                time.sleep(polling_interval)

            if pdf_content is None:
                raise TimeoutException("PDF response not found within timeout")
            
            log_message("PDF檔案從計劃書系統獲取中", queue, loop)

            pdf_file = io.BytesIO(pdf_content)
            with pdfplumber.open(pdf_file) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
            log_message("從PDF檔案中提取文本內容", queue, loop)

            age_1 = cash_value_info['age_1']
            age_2 = cash_value_info['age_2']
            print("age_1:", age_1)
            print("age_2:", age_2)
            
            currency_rate = float(calculation_data['inputs'].get('currencyRate', ''))
            age_1_cash_value = 0
            age_2_cash_value = 0
            annual_premium = 0
            
            log_message(f"基本儲蓄計劃是={basicPlan_}", queue, loop)
            
            system_prompt = (
                f"首先幫我在第1頁的資料表中找出第一項基本計劃的投保時每年保費的數值"
                f"如果找到的數值是美元,就要使用{currency_rate}匯率轉為港元, 答案就顯示美元及港元 **USDxxxxxx** 及 **HKDxxxxxx**"
                f"之後如果計劃是{basicPlan_}幫我在「款項提取說明－退保價值」表格中找出{str(age_1)}歲和{str(age_2)}歲的「款項提取後的退保價值總額(C) + (D)」的數值,"
                f"但如果計劃是{basicPlan_}幫我在「款項提取說明－退保價值」表格中找出{str(age_1)}歲和{str(age_2)}歲的「款項提取後的退保價值總額(A) + (B) +(C) + (D)」的數值,"
                f"如果找到的數值是美元,就要使用{currency_rate}匯率轉為港元, 答案就顯示美元及港元"
                f"答案要儘量簡單直接輸出兩句, 不要隔行:'{str(age_1)}歲的「款項提取後的退保價值總額是 **USDxxxxxx** 及 **HKDxxxxxx**'"
                f"'{str(age_2)}歲的「款項提取後的退保價值總額是 **USDxxxxxx** 及 **HKDxxxxxx**',"
                "答案要使用點格式"
                "數值前面要加上2個*號及HKD, 更加要有','作為貨幣模式"
                "最后答案用要講出答案是從哪一頁找到"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
            log_message("AI 解讀計劃書中, 請稍後...", queue, loop)
            
            if UseGrok:
                api_key = GROK2_API_KEY
                base_url="https://api.x.ai/v1"
                model = "grok-3-beta"
                log_message(f"AI模型=X", queue, loop)
            else: 
                api_key = DEEPSEEK_API_KEY   
                base_url="https://api.deepseek.com"
                model = "deepseek-chat"
                log_message(f"AI模型C使用中", queue, loop)
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
            ai_response = response.choices[0].message.content
            
            print("currency_rate",currency_rate)
            print("ai_response",ai_response)
            pattern = r'(?:HK?D?|K)\s*(\d[\d,]*)' 
            matches = re.findall(pattern, ai_response)
            
            if len(matches) >= 3:
                annual_premium =   int(matches[0].replace(',', ''))
                age_1_cash_value = int(matches[1].replace(',', ''))
                age_2_cash_value = int(matches[2].replace(',', ''))
            else:
                log_message("未能從AI回應中提取足夠的HKD值", queue, loop)
                annual_premium = 0
                age_1_cash_value = 0
                age_2_cash_value = 0
                
            log_message(f"投保時每年保費={annual_premium}", queue, loop)
            log_message(f"age_1_退保價值總額={age_1_cash_value}", queue, loop)
            log_message(f"age_2_退保價值總額={age_2_cash_value}", queue, loop)
            
            lines = ai_response.splitlines()
            for line in lines:
                log_message(f"AI 回覆 : {line}", queue, loop)
                
            log_message("建議書已成功建立及下載到計劃書系統中!", queue, loop)

            # Stop timer and log elapsed time
            end_time = time.time()
            start_time = sessions[session_id]['start_time']
            elapsed_time = end_time - start_time
            minutes, seconds = divmod(elapsed_time, 60)
            timer_value = f"{int(minutes):02d}:{int(seconds):02d}"
            log_message(f"v1.0 所需時間 = {timer_value}", queue, loop)

            return {
                "status": "success",
                "age_1_cash_value": age_1_cash_value,
                "age_2_cash_value": age_2_cash_value,
                "annual_premium": annual_premium
            }

    except TimeoutException as e:
        log_message(f"Error: {str(e)}", queue, loop)
        raise Exception(str(e))

# Worker to verify OTP and fill form
def verify_otp_worker(session_id: str, otp: str, calculation_data: Dict, form_data: Dict, cash_value_info: Dict, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    session_data = sessions.get(session_id)
    if not session_data or "driver" not in session_data:
        log_message("Invalid session ID", queue, loop)
        raise ValueError("Invalid session ID")
    driver = session_data["driver"]
    session_data["form_data"] = form_data
    session_data["calculation_data"] = calculation_data
    session_data["cash_value_info"] = cash_value_info

    try:
        otp = otp.strip()
        for i in range(6):
            pin_xpath = f'//*[@id="pin_{i}"]'
            otp_pin = WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, pin_xpath))
            )
            otp_pin.send_keys(otp[i])
            log_message(f"一次性密碼_{otp[i]} 已輸入", queue, loop)

        otp_continual_button = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="verify"]/div[2]/button[1]'))
        )
        driver.execute_script("arguments[0].click();", otp_continual_button)
        log_message("繼續 已點選, 請稍後...", queue, loop)

        # Start the timer
        start_time = time.time()
        sessions[session_id]['start_time'] = start_time

        try:
            WebDriverWait(driver, 20).until(
                lambda d: d.find_element(By.XPATH, "//button[.//span[text()='製作建議書']]")
            )
        except TimeoutException:
            log_message("您輸入的一次性密碼不正確", queue, loop)
            raise Exception("您輸入的一次性密碼不正確")

        proposal_button = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='製作建議書']]"))
        )
        proposal_button.click()
        log_message("計劃書按鍵 已點選", queue, loop)

        if form_data['isCorporateCustomer']:
            isCorporateCustomer_field = WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located((By.ID, "mat-mdc-checkbox-1-input"))
            )
            isCorporateCustomer_field.click()
            log_message("已點選 isCorporateCustomer checkbox", queue, loop)

        if form_data['isPolicyHolder']:
            isPolicyHolder_field = WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located((By.ID, 'mat-radio-5-input'))
            )
            isPolicyHolder_field.click()
            log_message("是保單持有人", queue, loop)
        else:
            isPolicyHolder_field = WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located((By.ID, 'mat-radio-6-input'))
            )
            isPolicyHolder_field.click()
            log_message("不是保單持有人", queue, loop)

        sureName_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//div[label[contains(text(), "英文姓氏")]]//input'))
        )
        sureName_field.clear()
        sureName_field.send_keys(str(form_data['surname']))
        log_message("英文姓氏 已填", queue, loop)

        givenName_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//div[label[contains(text(), "英文名字")]]//input'))
        )
        givenName_field.clear()
        givenName_field.send_keys(str(form_data['givenName']))
        log_message("英文名字 已填", queue, loop)

        if form_data['chineseName']:
            chineseName_field = WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, '//div[label[contains(text(), "中文姓名")]]//input'))
            )
            chineseName_field.clear()
            chineseName_field.send_keys(str(form_data['chineseName']))
            log_message("中文姓名 已填", queue, loop)

        age_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//div[label[contains(text(), "投保年齡")]]//input'))
        )
        age_field.clear()
        age_field.send_keys(str(calculation_data['inputs'].get('age', '')))
        log_message(f"投保人年齡 已填={str(calculation_data['inputs'].get('age', ''))}", queue, loop)

        if "Female" in form_data['gender']:
            gender_field = WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, "//mat-radio-button[@value='Female']"))
            )
            gender_field.click()
            log_message("性別 女 已點選", queue, loop)

        if form_data['isSmoker']:
            isSmoker_field = WebDriverWait(driver, TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, "//mat-radio-button[@value='Yes']"))
            )
            isSmoker_field.click()
            log_message("你是否有吸煙習慣 是 已點選", queue, loop)

        basicPlan_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/qq-left-tab/div/button[2]/span[2]/div'))
        )
        basicPlan_field.click()
        log_message("基本計劃 頁 已點選", queue, loop)

        def log_func(message):
            log_message(message, queue, loop)
            
        basicPlan_ = str(form_data['basicPlan'])
        print(f"basicPlan = {basicPlan_}")
        if 'GS' in basicPlan_:
            fill_GS_form(driver, form_data, calculation_data, log_func, TIMEOUT)
        elif 'LV' in basicPlan_:
            fill_LV_form(driver, form_data, calculation_data, log_func, TIMEOUT)     
        
        log_message(f"已完成填寫 {basicPlan_}", queue, loop)
        result = perform_checkout(driver, form_data['notionalAmount'], form_data, queue, loop, calculation_data, cash_value_info, session_id)
        
        if result["status"] == "success":
            driver.quit()
            sessions.pop(session_id, None)
            session_queues.pop(session_id, None)
        return result

    except Exception as e:
        log_message(f"Error in verify_otp_worker: {str(e)}", queue, loop)
        driver.quit()
        sessions.pop(session_id, None)
        session_queues.pop(session_id, None)
        raise

# Worker to retry with a new notional amount
def retry_notional_worker(session_id: str, new_notional_amount: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    session_data = sessions.get(session_id)
    if not session_data or "driver" not in session_data or "form_data" not in session_data:
        log_message("Invalid session ID", queue, loop)
        raise ValueError("Invalid session ID")
    driver = session_data["driver"]
    form_data = session_data["form_data"]
    calculation_data = session_data["calculation_data"]
    cash_value_info = session_data["cash_value_info"]

    try:
        basicPlan_field = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/qq-left-tab/div/button[2]/span[2]/div'))
        )
        basicPlan_field.click()
        log_message("基本計劃 page 已點選", queue, loop)

        nominalAmount_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, "//label[contains(text(), '名義金額')]/ancestor::qq-notional-amount//input"))
        )
        nominalAmount_field.clear()
        nominalAmount_field.send_keys(new_notional_amount)
        log_message(f"新的名義金額 已填上 {new_notional_amount}", queue, loop)

        result = perform_checkout(driver, new_notional_amount, form_data, queue, loop, calculation_data, cash_value_info, session_id)
        
        if result["status"] == "success":
            driver.quit()
            sessions.pop(session_id, None)
            session_queues.pop(session_id, None)
        return result

    except Exception as e:
        log_message(f"Error in retry_notional_worker: {str(e)}", queue, loop)
        driver.quit()
        sessions.pop(session_id, None)
        session_queues.pop(session_id, None)
        raise

# Helper function to get medical premium
def get_medical_premium(processed_data, start_year_number):
    try:
        if not isinstance(processed_data, list):
            return None
        for entry in processed_data:
            if not isinstance(entry, dict):
                continue
            if entry.get('yearNumber') == int(start_year_number) and 'medicalPremium' in entry:
                return entry['medicalPremium']
        return None
    except Exception as e:
        return None

# FastAPI endpoints
@app.post("/init-session")
async def init_session():
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    session_queues[session_id] = queue
    return {"session_id": session_id}

@app.post("/login")
async def initiate_login(request: LoginRequest):
    session_id = request.session_id
    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail="Session not found")
    queue = session_queues[session_id]
    loop = asyncio.get_running_loop()
    try:
        await run_in_thread(
            selenium_worker,
            session_id,
            request.url,
            request.username,
            request.password,
            queue,
            loop
        )
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-otp")
async def verify_otp(request: OtpRequest):
    session_id = request.session_id
    queue = session_queues.get(session_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Session not found")
    loop = asyncio.get_running_loop()
    try:
        result = await run_in_thread(
            verify_otp_worker,
            session_id,
            request.otp,
            request.calculation_data.dict(),
            request.formData.dict(),
            request.cashValueInfo.dict(),
            queue,
            loop
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/retry-notional")
async def retry_notional(request: RetryRequest):
    session_id = request.session_id
    queue = session_queues.get(session_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Session not found")
    loop = asyncio.get_running_loop()
    try:
        result = await run_in_thread(
            retry_notional_worker,
            session_id,
            request.new_notional_amount,
            queue,
            loop,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# SSE endpoint for logs
@app.get("/logs/{session_id}")
async def stream_logs(session_id: str):
    queue = session_queues.get(session_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        while True:
            message = await queue.get()
            yield f"data: {message}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Data retrieval endpoint
class CalculationRequest(BaseModel):
    company: str
    planFileName: str
    age: int
    planOption: str
    numberOfYears: int

class OutputData(BaseModel):
    yearNumber: int
    age: int
    medicalPremium: float

@app.post("/getData", response_model=List[OutputData])
async def get_data(request: CalculationRequest):
    try:
        print("request.company=", request.company)
        json_file = os.path.join(
            "plan2/Manulife/",
            # request.company,
            f"{request.planFileName}.json"
        )
        
        print("request.planFileName=", request.planFileName)
        print("request.planOption=", request.planOption)
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        max_age = 100
        max_years = max(max_age - request.age + 1, 1)
        result = []
        for year in range(1, max_years + 1):
            current_age = request.age + year - 1
            if str(current_age) not in data[str(request.planOption)]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Premium data not found for age {current_age}"
                )
            result.append({
                "yearNumber": year,
                "age": current_age,
                "medicalPremium": data[str(request.planOption)][str(current_age)]
            })
        return result
    except FileNotFoundError:
        logger.error(f"JSON file not found: {json_file}")
        raise HTTPException(status_code=404, detail="Plan data not found")
    except KeyError as e:
        logger.error(f"Invalid key: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except json.JSONDecodeError:
        logger.error("JSON decode error")
        raise HTTPException(status_code=500, detail="Invalid JSON data")