import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from sc_click import sc_click

def fill_GS_form(driver, form_data, calculation_data, log_func, TIMEOUT=120):
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
        except Exception:
            return None

    basicPlan_select_field = WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.XPATH, "//label[contains(text(), '基本計劃')]/following-sibling::mat-form-field//mat-select"))
    )
    driver.execute_script("arguments[0].click();", basicPlan_select_field)
    log_func("基本計劃 下拉式選單已點選")
    
    basicPlan = str(form_data['basicPlan'])
    print(f"basicPlan = {basicPlan}")
    if 'GS' in str(form_data['basicPlan']):
        basicPlan_option_field = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='mat-select-4-panel']//mat-option[.//span[contains(text(), '(GS)')]]"))
        )
        basicPlan_option_field.click()
        log_func("基本計劃 GS 選項 已點選")

    numberOfYear_select_field = WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.XPATH, "//label[contains(text(), '保費繳付期')]/following-sibling::mat-form-field//mat-select"))
    )
    driver.execute_script("arguments[0].click();", numberOfYear_select_field)
    log_func("保費繳付期 下拉式選單已點選")

    number_of_years = str(form_data['premiumPaymentPeriod'])
    log_func(f"number_of_years={number_of_years}")

    if '3' in number_of_years:
        numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "3")]'))
        )
        numberOfYear_option_field.click()
        log_func("保費繳付期 3 year 已點選")
    elif '15' in number_of_years:
        numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "15")]'))
        )
        numberOfYear_option_field.click()
        log_func("保費繳付期 15 year 已點選")
    elif '10' in number_of_years:
        numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "10")]'))
        )
        numberOfYear_option_field.click()
        log_func("保費繳付期 10 year 已點選")
    elif '5' in number_of_years:
        numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "5")]'))
        )
        numberOfYear_option_field.click()
        log_func("保費繳付期 5 year 已點選")

    worryFreeSelection = WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.XPATH, "//label[contains(text(), '無憂選')]/following-sibling::mat-form-field//mat-select"))
    )
    driver.execute_script("arguments[0].click();", worryFreeSelection)
    log_func("無憂選 下拉式選單已點選")

    worryFreeOption = WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.XPATH, "//div[@id='mat-select-8-panel']//mat-option[.//span[contains(text(), '否')]]"))
    )
    driver.execute_script("arguments[0].click();", worryFreeOption)
    log_func("無憂選 否 已點選")

    if "美元" in form_data['currency']:
        currency_select_field = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//label[contains(text(), '貨幣')]/following-sibling::mat-form-field//mat-select"))
        )
        driver.execute_script("arguments[0].click();", currency_select_field)
        log_func("貨幣 下拉式選單已點選")
        currency_option_field = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='mat-select-10-panel']//mat-option[.//span[contains(text(), '美元')]]"))
        )
        currency_option_field.click()
        log_func("美元 選項 已點選")

    nominalAmount_field = WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.XPATH, "//label[contains(text(), '名義金額')]/ancestor::qq-notional-amount//input"))
    )
    nominalAmount_field.clear()
    nominalAmount_field.send_keys(str(form_data['notionalAmount']))
    log_func("名義金額 輸入欄已填")

    if '每年' not in form_data['premiumPaymentMethod']:
        premiumPaymentMethod_select_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.ID, 'mat-select-value-13'))
        )
        premiumPaymentMethod_select_field.click()
        log_func("保費繳付方式 下拉式選單已點選")
        if '每半年' in form_data['premiumPaymentMethod']:
            numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "每半年")]'))
            )
            numberOfYear_option_field.click()
            log_func("保費繳付方式 每半年")
        elif '每季' in form_data['premiumPaymentMethod']:
            numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "每季")]'))
            )
            numberOfYear_option_field.click()
            log_func("保費繳付方式 每季")
        elif '每月' in form_data['premiumPaymentMethod']:
            numberOfYear_option_field = WebDriverWait(driver, TIMEOUT).until(
                EC.visibility_of_element_located((By.XPATH, '//mat-option[contains(., "每月")]'))
            )
            numberOfYear_option_field.click()
            log_func("保費繳付方式 每月")
    
    sc_click(driver,log_func,'/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/qq-left-tab/div/button[6]/span[2]/div', "補充利益說明頁 已點選")
        
    # xpath = '/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/qq-left-tab/div/button[6]/span[2]/div'
    # try:
    #     # log_func("Here 21")
    #     # Wait for the element to be visible and interactable
    #     you_hope_field_2 = WebDriverWait(driver, 10).until(
    #         EC.element_to_be_clickable((By.XPATH, xpath))
    #     )
    #     # log_func("Here 22")
    #     # Scroll to the element
    #     driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", you_hope_field_2)
    #     # Wait again to ensure the element is still clickable after scrolling
    #     WebDriverWait(driver, 10).until(
    #         EC.element_to_be_clickable((By.XPATH, xpath))
    #     )
    #     # log_func("Here 23")
    #     # Optional: Small delay to allow any animations to settle
    #     time.sleep(1)  # Reduced from 5s to 1s to minimize unnecessary wait
    #     # Attempt to click the element
    #     you_hope_field_2.click()
    #     # log_func("Here 24")
    #     log_func("補充利益說明頁 已點選")

    # except ElementClickInterceptedException:
    #     # log_func("Here 25")
    #     log_func("Click intercepted, attempting JavaScript click...")
    #     # Retry with JavaScript click
    #     driver.execute_script("arguments[0].click();", you_hope_field_2)
    #     # log_func("Here 26")
    #     log_func("JS Click successful")

    # except TimeoutException:
    #     # log_func("Here 27")
    #     log_func("Element not found or not clickable within timeout")
    #     raise
    
    # supplimentary_field = WebDriverWait(driver, TIMEOUT).until(
    #     EC.visibility_of_element_located((By.XPATH, '/html/body/app-root/qq-base-structure/mat-drawer-container/mat-drawer-content/div/div/div/qq-left-tab/div/button[6]/span[2]/div'))
    # )
    
    # supplimentary_field.click()
    # log_func("補充利益說明頁 已點選")
    
    sc_click(driver,log_func,"//label[contains(text(), '是')]", "是 已點選")
    # xpath = "//label[contains(text(), '是')]"
    # try:
    #     # log_func("Here 21")
    #     # Wait for the element to be visible and interactable
    #     you_hope_field_2 = WebDriverWait(driver, 10).until(
    #         EC.element_to_be_clickable((By.XPATH, xpath))
    #     )
    #     # log_func("Here 22")
    #     # Scroll to the element
    #     driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", you_hope_field_2)
    #     # Wait again to ensure the element is still clickable after scrolling
    #     WebDriverWait(driver, 10).until(
    #         EC.element_to_be_clickable((By.XPATH, xpath))
    #     )
    #     # log_func("Here 23")
    #     # Optional: Small delay to allow any animations to settle
    #     time.sleep(1)  # Reduced from 5s to 1s to minimize unnecessary wait
    #     # Attempt to click the element
    #     you_hope_field_2.click()
    #     # log_func("Here 24")
    #     log_func("是 已點選")

    # except ElementClickInterceptedException:
    #     # log_func("Here 25")
    #     log_func("Click intercepted, attempting JavaScript click...")
    #     # Retry with JavaScript click
    #     driver.execute_script("arguments[0].click();", you_hope_field_2)
    #     # log_func("Here 26")
    #     log_func("JS Click successful")

    # except TimeoutException:
    #     # log_func("Here 27")
    #     log_func("Element not found or not clickable within timeout")
    #     raise
    
    # you_hope_field = WebDriverWait(driver, TIMEOUT).until(
    #     EC.element_to_be_clickable((By.XPATH, "//label[contains(text(), '是')]"))
    # )
    # you_hope_field.click()
    # log_func("提取說明 已點選")
    sc_click(driver,log_func,"//mat-label[span[text()='提取選項']]/following-sibling::mat-radio-group//label[span[text()='指定提取金額']]", "指定提取金額1 已點選")
    # xpath = "//mat-label[span[text()='提取選項']]/following-sibling::mat-radio-group//label[span[text()='指定提取金額']]"
    # try:
    #     element = WebDriverWait(driver, 10).until(
    #         EC.presence_of_element_located((By.XPATH, xpath))
    #     )
    #     driver.execute_script("arguments[0].scrollIntoView(true);", element)
    #     WebDriverWait(driver, 10).until(
    #         EC.element_to_be_clickable((By.XPATH, xpath))
    #     )
    #     element.click()
    #     log_func("指定提取金額1 已點選")
    # except ElementClickInterceptedException:
    #     log_func("Click intercepted, attempting JavaScript click...")
    #     driver.execute_script("arguments[0].click();", element)
    #     log_func("JS Click successful")
    sc_click(driver,log_func,"//mat-label[span[text()='請選擇您的提取款項由']]/following-sibling::mat-radio-group//label[.//span[text()='保單年度']]", "保單年度 已點選")
    # withdraw_start_from = WebDriverWait(driver, TIMEOUT).until(
    #     EC.element_to_be_clickable((By.XPATH, "//mat-label[span[text()='請選擇您的提取款項由']]/following-sibling::mat-radio-group//label[.//span[text()='保單年度']]"))
    # )
    # withdraw_start_from.click()
    # log_func("保單年度 已點選")
    continue_button = sc_click(driver,log_func,"//button[contains(., '繼續')]", "繼續 已點選")
    # continue_button = WebDriverWait(driver, TIMEOUT).until(
    #     EC.element_to_be_clickable((By.XPATH, "//button[contains(., '繼續')]"))
    # )
    # continue_button.click()
    # log_func("繼續 已點選")

    WebDriverWait(driver, TIMEOUT).until(EC.staleness_of(continue_button))
    time.sleep(1)

    startYearNumber = str(int(number_of_years) + 1)
    log_func(f"由(保單年度) = {startYearNumber}")
    numberOfWithDrawYear = str(100 - int(number_of_years) - int(calculation_data['inputs'].get('age', '')))
    log_func(f"提取期(年) = {numberOfWithDrawYear}")
    base_num = None

    for start_id in ['14', '19']:
        input_id = f"mat-input-{start_id}"
        try:
            input_field = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, input_id))
            )
            label = input_field.find_element(
                By.XPATH,
                ".//ancestor::mat-form-field/preceding-sibling::div[@class='mat-label-box']/mat-label"
            )
            if label.text.strip() == '由(保單年度)':
                base_num = start_id
                from_year_field = WebDriverWait(driver, 3).until(
                    EC.visibility_of_element_located((By.ID, f"{input_id}")))
                from_year_field.send_keys(startYearNumber)
                log_func(f"由(保單年度) 已填(14/19) base_num= {str(base_num)}")
                break
        except TimeoutException:
            log_func(f"ID mat-input-{input_id} 未找到，嘗試下一個...")
            continue

    if base_num is None:
        for i in range(13, 31):
            input_id = f"mat-input-{i}"
            try:
                input_field = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.ID, input_id))
                )
                label = input_field.find_element(
                    By.XPATH,
                    ".//ancestor::mat-form-field/preceding-sibling::div[@class='mat-label-box']/mat-label"
                )
                if label.text.strip() == '由(保單年度)':
                    base_num = i
                    from_year_field = WebDriverWait(driver, 3).until(
                        EC.visibility_of_element_located((By.ID, f"{input_id}")))
                    from_year_field.send_keys(startYearNumber)
                    log_func(f"由(保單年度) 已填 {startYearNumber} 及 base_num = {str(base_num)}")
                    break
            except Exception:
                continue

    field_ids = {
        'takeout_year': f"mat-input-{int(base_num) + 1}",
        'every_year_amount': f"mat-input-{int(base_num) + 2}",
        'inflation': f"mat-input-{int(base_num) + 3}"
    }

    
    takeout_year_field = WebDriverWait(driver, TIMEOUT).until(
        EC.visibility_of_element_located((By.ID, field_ids['takeout_year'])))
    takeout_year_field.clear()
    takeout_year_field.send_keys(numberOfWithDrawYear)
    log_func(f"提取期(年) 已填 with ID {field_ids['takeout_year']}")

    every_year_amount_field = WebDriverWait(driver, TIMEOUT).until(
        EC.visibility_of_element_located((By.ID, field_ids['every_year_amount'])))
    every_year_amount_field.clear()
    if not form_data['useInflation']:
        every_year_amount_field.send_keys('1000')
    else:
        premium = get_medical_premium(calculation_data['processedData'], startYearNumber)
        if "美元" in form_data['currency']:
            currency_rate = float(calculation_data['inputs'].get('currencyRate', ''))
            premium = round(premium / currency_rate, 0)
        every_year_amount_field.send_keys(str(int(premium)))
    log_func(f"每年提取金額 已填 with ID {field_ids['every_year_amount']}")

    if form_data['useInflation']:
        inflation_rate = str(calculation_data['inputs'].get('inflationRate', ''))
        inflation_field = WebDriverWait(driver, TIMEOUT).until(
            EC.visibility_of_element_located((By.ID, field_ids['inflation']))
        )
        inflation_field.clear()
        inflation_field.send_keys(inflation_rate)
        log_func(f"通貨膨脹率 已填 with ID {field_ids['inflation']}")

    enter_button = WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.XPATH, "//span[text()='加入']"))
    )
    driver.execute_script("arguments[0].click();", enter_button)
    log_func("加入 已點選, 請稍後...")

    time.sleep(3)
    try:
        print("startYearNumber", startYearNumber)
        age = int(calculation_data['inputs'].get('age', ''))
        print("age", age)
        searchAge = int(startYearNumber) + age
        print("searchAge", searchAge)
        
        start_year_str = str(startYearNumber)
        search_age_str = str(searchAge)
        print(f"保單年度終結/歲數 = {start_year_str}/{search_age_str}")
        
        input_element = driver.find_element(
            By.XPATH,
            f"//div[normalize-space(text())='{start_year_str}/{search_age_str}']/following::input[starts-with(@id, 'mat-input-') and @inputmode='numeric']"
        )
        input_id = input_element.get_attribute("id")
        print("input_id_1:", input_id)

        id = int(input_id.split('-')[-1])
        print("input_id_2:", str(id))

        id = id + 3
        print("input_id_3:", str(id))

        log_func(f"元素的 ID 是 {id}")

    except Exception as e:
        print(f"Error finding input element: {e}")
        log_func(f"Error finding input element: {e}")
        driver.quit()
        raise

    if not form_data['useInflation']:
        sorted_data = sorted(calculation_data['processedData'], key=lambda x: x['yearNumber'])
        # log_func(f"sorted_data={sorted_data}")
        start_index = next((i for i, item in enumerate(sorted_data) if item['yearNumber'] == int(startYearNumber)), None)
        # print(f"start_index={start_index}")
        if start_index is None:
            raise ValueError(f"Start year {startYearNumber} not found in processedData")
        end_index = start_index + int(numberOfWithDrawYear)
        # print(f"end_index={end_index}")
        withdrawal_data = sorted_data[start_index:end_index]
        # print(f"withdrawal_data={withdrawal_data}")
        currency_rate = float(calculation_data['inputs'].get('currencyRate', ''))

        for idx, entry in enumerate(withdrawal_data):
            # print(f"idx={idx}")
            # print(f"entry={entry}")
            premium = entry['medicalPremium']
            # print(f"premium={premium}")
            if "美元" in form_data['currency']:
                premium = round(premium / currency_rate, 0)
            try:    
                input_index = id + (idx * 5)
                xpath = f'//*[@id="mat-input-{input_index}"]'
                input_field = WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.XPATH, xpath))
                )
                # Scroll to the element
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", input_field)
                input_field.clear()
                input_field.send_keys(str(int(premium)))
                inputed_id = input_field.get_attribute("id")
                log_func(f"已填 {str(int(start_year_str)+idx)}/{str(int(search_age_str)+idx)}({premium}) in field index = {input_index} and inputed_id = {inputed_id}")
                
                time.sleep(0.2)
            except Exception as e:
                print(f"Error entring input element: {e}")    
                input_index = 28 + (idx * 5)
                xpath = f'//*[@id="mat-input-{input_index}"]'
                input_field = WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.XPATH, xpath))
                )
                # Scroll to the element
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", input_field)
                input_field.clear()
                input_field.send_keys(str(int(premium)))
                inputed_id = input_field.get_attribute("id")
                log_func(f"已填 {str(int(start_year_str)+idx)}/{str(int(search_age_str)+idx)}({premium}) in field index = {input_index} and inputed_id = {inputed_id}")
                
                time.sleep(0.2)
            
        time.sleep(1)