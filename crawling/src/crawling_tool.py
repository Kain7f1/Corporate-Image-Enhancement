import re
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
import datetime
import utility_module as util

# dcinside 봇 차단을 위한 헤더 설정
header_dc = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua-mobile": "?0",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }


###############################
# get_search_result()
# 기능 : 검색결과 페이지 정보를 불러온다
# 리턴값 : 검색결과의 글 리스트
def get_search_result(search_url, time_sleep=0):
    try:
        with requests.Session() as session:
            response = session.get(search_url, headers=header_dc)
        soup = BeautifulSoup(response.text, "html.parser")  # 검색 결과 페이지
        element_list = soup.select("table.gall_list tr.ub-content")  # 한 페이지 전체 글 리스트
        if len(element_list) == 0:  # 검색 결과는 광고글를 포함해서 최소 1개 이상이어야 한다. 없으면 다시 돌림
            print("[검색 실패해서 반복합니다] [get_search_result()]")
            element_list = get_search_result(search_url, time_sleep+2)
    except Exception as e:
        print("[오류가 발생하여 반복합니다] [get_search_result()] ", e)
        element_list = get_search_result(search_url, time_sleep+2)
    return element_list


###############################
# get_max_num()
# 기능 : 검색결과 중 가장 큰 글번호를 구하여 리턴한다
# 리턴값 : max_num
def get_max_num(gall_url, gall_id, time_sleep=0):
    gall_type = get_gall_type(gall_url)     # "minor" or "mini" or "major"
    try:
        with requests.Session() as session:
            response = session.get(gall_url, headers=header_dc)
            time.sleep(time_sleep)
        soup = BeautifulSoup(response.text, "html.parser")  # 페이지의 soup
        box = soup.select("div.gall_listwrap tr.ub-content")        # 글만 있는 box
        first_content = ''
        # 검색 범위를 정하는 작업
        for content in box:
            # 광고, 공지는 제거한다
            if gall_type == "major":    # 메이저 갤러리
                gall_num = content.find('td', class_='gall_num').get_text()
                if gall_num in ["설문", "AD", "공지"]:
                    continue
            else:   # 마이너, 미니 갤러리
                gall_subject = content.find('td', class_='gall_subject').get_text()
                if gall_subject in ["설문", "AD", "공지"]:
                    continue
            # 광고, 공지를 제외한 가장 첫번째 글
            first_content = content.select_one("td.gall_num").get_text()
            break
        max_num = int(int(first_content)/10000+1)*10000      # max_num  의 글번호까지 검색한다
    except Exception as e:
        print(f"[오류가 발생하여 반복합니다] [get_max_num(time_sleep={time_sleep})] ", e)
        max_num = get_max_num(gall_url, gall_id, time_sleep+2)
    return max_num


#####################################
def get_new_row_from_search_result(element, gall_id, blacklist, error_count=0):
    new_row = []
    is_continue = False     # is_continue가 True면 이 함수를 사용하는 반복문을 탈출하도록 할 것입니다
    try:
        if error_count >= 3:    # 3번 반복해도 실패하면 넘어가기
            print("에러가 3번 발생해서 스킵합니다. 함수 : get_new_row_from_search_result()")
            is_continue = True
            return is_continue, new_row  # 넘어가기
        if element.find('td', class_='gall_writer').get_text() == "운영자":  # 광고글은 글쓴이가 "운영자"
            print("광고글입니다. 다음글로 넘어갑니다")
            is_continue = True              # 페이지마다 광고글 처리하기
            return is_continue, new_row     # 광고글은 넘어가기
        date = element.find('td', class_='gall_date')['title'][:10]  # date 가져오기
        title = element.find('td', class_='gall_tit ub-word').find('a').get_text(strip=True)  # title 가져오기
        title = util.preprocess_title(title)  # 제목을 전처리하기
        if util.contains_blacklist(title, blacklist):
            print("제목에 blacklist에 해당하는 단어 발견 : ", title)    # 제목에 blacklist에 해당하는 단어 발견
            is_continue = True              # 제목에 blacklist의 단어가 있으면
            return is_continue, new_row     # 무시하고 넘어가기
        url = "https://gall.dcinside.com" + element.select_one("td.gall_tit a")['href']
        new_row = [date, title, url, gall_id]
    except Exception as e:
        print("[오류가 발생하여 반복합니다] [get_new_row_from_search_result()] ", e)
        is_continue, new_row = get_new_row_from_search_result(element, gall_id, blacklist, error_count+1)
    return is_continue, new_row

#####################################
# 본문에서 new_row를 얻어오는 함수
def get_new_row_from_main_content(url_row, time_sleep=0):
    is_comment = 0  # 본문이므로 0
    try:
        with requests.Session() as session:
            response = session.get(url_row['url'], headers=header_dc)
            time.sleep(time_sleep)
        soup = BeautifulSoup(response.text, "html.parser")
        content = util.preprocess_content_dc(soup.find('div', {"class": "write_div"}).text)
        content = url_row['title'] + " " + content
        new_row = [url_row['date'], url_row['title'], url_row['url'], url_row['media'], content, is_comment]
    except Exception as e:
        print(f"[오류가 발생하여 반복합니다] [get_new_row_from_main_content(url_row, {time_sleep})] ", e)
        new_row = get_new_row_from_main_content(url_row, time_sleep+2)
    return new_row


#####################################
# 기능 : url을 받아 reply_list를 리턴합니다
# 리턴값 : reply_list
def get_reply_list(url, time_sleep=0):
    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(time_sleep)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        reply_list = soup.find_all("li", {"class": "ub-content"})
        driver.quit()
    except Exception as e:
        print(f"[오류가 발생하여 반복합니다] [get_reply_list(url, {time_sleep})] ", e)
        reply_list = get_reply_list(url, time_sleep+2)
    return reply_list


################################
# get_last_page()
# 기능 : [dcinside] 갤러리 내에서 검색결과의 마지막 페이지가 몇인지 리턴 (검색한 직후의 url이어야 함)
# 리턴값 : max_page(int)
def get_last_page(url, time_sleep=0):
    try:
        with requests.Session() as session:
            response = session.get(url, headers=header_dc)
            time.sleep(time_sleep)
        soup = BeautifulSoup(response.text, "html.parser").find("div", class_="bottom_paging_wrap re")
        filtered_a_tags = [a for a in soup.find_all('a') if not a.find('span', class_='sp_pagingicon')]
        num_button_count = len(filtered_a_tags) + 1    # 숫자 버튼의 개수

        if num_button_count >= 16:    # 한번에 15 page씩 나와서, page가 16개 이상이면 >> 버튼이 생기면서 a태그가 17개가 된다 / 이때의 페이징 처리
            last_page_url = soup.find_all("a")[-2]['href']                          # 맨 마지막 페이지로 가는 버튼의 url
            last_page = re.search(r'page=(\d+)', last_page_url).group(1)     # 정규식으로 page 부분의 숫자만 추출
            last_page = int(last_page)                                              # 맨 마지막 페이지
        else:
            last_page = num_button_count
    except Exception as e:
        print(f"[오류가 발생하여 반복합니다] [get_last_page(url, {time_sleep})] ", e)
        last_page = get_last_page(url, time_sleep+2)
    return last_page


##############################
# get_gall_id()
# 기능 : gall_url을 받아 gall_id를 리턴한다
def get_gall_id(gall_url):
    return re.search(r'id=([\w_]+)', gall_url).group(1)


#############################
# get_gall_type()
# 기능 : 메이저갤러리인지 마이너갤러리인지 미니갤러리인지 리턴한다
# 리턴값 : gall_type 문자열
def get_gall_type(gall_url):
    if "mgallery" in gall_url:  # 마이너갤러리
        gall_type = "minor"
    elif "mini" in gall_url:    # 미니갤러리
        gall_type = "mini"
    else:                       # 메이저갤러리
        gall_type = "major"
    return gall_type


##############################
# get_url_base()
# 기능 : 메이저갤러리인지 마이너갤러리인지 미니갤러리인지 판단한다
# 리턴값 : url_base
def get_url_base(gall_url):
    if "mgallery" in gall_url:  # 마이너갤러리
        url_base = "https://gall.dcinside.com/mgallery"
    elif "mini" in gall_url:    # 미니갤러리
        url_base = "https://gall.dcinside.com/mini"
    else:                       # 메이저갤러리
        url_base = "https://gall.dcinside.com"
    return url_base


#####################################
# 기능 : 댓글 html코드를 받아서, 댓글의 date를 리턴합니다
# 리턴값 : 2023-10-06 형식의 문자열
def get_reply_date(reply):
    temp_date = reply.find("span", {"class": "date_time"}).text.replace(".", "-")  # 댓글 등록 날짜 추출
    if temp_date[:2] == "20":  # 작년 이전은 "2022.09.07 10:10:54" 형식임
        date = temp_date[:10]
    else:  # 올해는 "09.30 10:10:54" 형식임
        date = str(datetime.datetime.now().year) + "-" + temp_date[:5]  # 올해 년도를 추가함
    return date


#####################################
# 기능 : 무시해야하는 댓글이면, True를 반환하고, 필요한 댓글이면 False를 반환합니다
def is_ignore_reply(reply):
    if reply.select_one("p.del_reply"):
        print("[삭제된 코멘트입니다]")
        return True
    elif reply.find('span', {'data-nick': '댓글돌이'}):
        print("[댓글돌이는 무시합니다]")
        return True
    elif reply.find('div', {'class': 'comment_dccon'}):
        print("[디시콘은 무시합니다]")
        return True
    else:
        return False


#############################
# get_driver()
# 사용 전제 조건 : Users 폴더에 버전에 맞는 chromedriver.exe를 다운받아주세요
# 기능 : driver를 반환합니다
# 리턴값 : driver
# 사용법 : driver = get_driver() 쓰고 driver.get(url) 처럼 사용합니다
def get_driver():
    CHROME_DRIVER_PATH = "C:/Users/chromedriver.exe"    # (절대경로) Users 폴더에 chromedriver.exe를 설치했음
    options = webdriver.ChromeOptions()                 # 옵션 선언
    # 옵션 설정
    # options.add_argument("--start-maximized")         # 창이 최대화 되도록 열리게 한다.
    options.add_argument("--headless")                  # 창이 없이 크롬이 실행이 되도록 만든다
    options.add_argument("disable-infobars")            # 안내바가 없이 열리게 한다.
    options.add_argument("disable-gpu")                 # 크롤링 실행시 GPU를 사용하지 않게 한다.
    options.add_argument("--disable-dev-shm-usage")     # 공유메모리를 사용하지 않는다
    options.add_argument("--blink-settings=imagesEnabled=false")    # 이미지 로딩 비활성화
    options.add_argument('--disk-cache-dir=/path/to/cache-dir')     # 캐시 사용 활성화
    options.page_load_strategy = 'none'     # 전체 페이지가 완전히 로드되기를 기다리지 않고 다음 작업을 수행 (중요)
    options.add_argument('--log-level=3')   # 웹 소켓을 통한 로그 메시지 비활성화
    options.add_argument('--no-sandbox')    # 브라우저 프로파일링 비활성화
    options.add_argument('--disable-plugins')       # 다양한 플러그인 및 기능 비활성화
    options.add_argument('--disable-extensions')    # 다양한 플러그인 및 기능 비활성화
    options.add_argument('--disable-sync')          # 다양한 플러그인 및 기능 비활성화
    driver = webdriver.Chrome(CHROME_DRIVER_PATH, options=options)
    return driver









