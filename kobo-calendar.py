import requests
from bs4 import BeautifulSoup
import re
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz

def request_with_agent(url):
#     Need to use User-Agent to get the data
#     user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    user_agent = "kobo"
    res = requests.get(url, headers={"User-Agent": user_agent})
    return res

def get_start_thursday(month, day):
    current_date = datetime.today()
    start_date = None
    for i in [-1, 0, 1]:
        checked = datetime(current_date.year + i, month, day)
        delta = current_date - checked
#         only accept the recent event
#         Monday is 0
        if checked.weekday() == 3 and abs(delta.days) < 14:
            start_date = checked
            break
    assert(start_date)
    return start_date

def generate_ics(title, book_link, promo, date):
    cal = Calendar()
    cal.add("prodid", "-//KOBO 99 calendar//")
    cal.add("version", "2.0")
    event = Event()
    event.add("summary", "KOBO99 {}".format(title))
#     url section does not show on google calendar
    event.add("description", "連結: {} 優惠碼: {}".format(book_link, promo))
#   pytz timezone might not supported by outlook https://icalendar.org/validator.htm
    utc_8 = pytz.timezone("Asia/Taipei")
    event.add("dtstart", datetime(date.year, date.month, date.day, 0,0, tzinfo=utc_8))
    event.add("dtend", datetime(date.year, date.month, date.day, 23,59, tzinfo=utc_8))
    event.add("dtstamp", datetime(date.year, date.month, date.day, 12, 0, tzinfo=utc_8))
    date_str = date.strftime("%Y-%m-%d")
    event["uid"] = "{}@kobo99".format(date_str)
    cal.add_component(event)
    return cal

def write_ics(folder, date, cal):
    filename = "{}/kobo-calendar-{:%Y-%m-%d}.ics".format(folder, date)
    with open(filename, "wb") as f:
        f.write(cal.to_ical())
    return filename

def generate_md_section(day, title, book_link, summary, img_link, promo, ics_file):
    md_str = "- {:%Y-%m-%d}: [{}]({})  \n".format(day, title, book_link)
    md_str += "  折扣碼: {} 提醒我: [ics]({})  \n".format(promo,ics_file)
    md_str += "  簡介: {}  \n".format(summary)
    md_str += '  <img width="200" src="{}">\n'.format(img_link)
    return md_str

def handle_list(url, start_thursday):
    response = request_with_agent(url)
    soup = BeautifulSoup(response.content, "html.parser")
    day_offset = 0
    md_content="# [kobo 99 清單]({})\n".format(url)
    csv_content=""
    for book in soup.find_all("div", class_="book-block"):

        summary_block = book.find_previous_sibling("div", class_="content-block").find_all("p")
        summary = ""
        for i in range(1, len(summary_block)):
            summary += summary_block[i].getText()
        book_link = book.find("a", class_="book-block__img").get("href")
        img_link = book.find("a", class_="book-block__img").find("img").get("src")
        title = book.find("span", class_="title").getText()
        promo = ""
        for text in book.find_all("p"):
            if m := re.match(r".*(kobo.*99)", text.getText()):
                promo = m.group(1)
        promo_day = start_thursday + timedelta(days=day_offset)
        ics = generate_ics(title, book_link, promo, promo_day)
        ics_file = write_ics("ics", promo_day, ics)
        md_content += generate_md_section(promo_day, title, book_link, summary, img_link, promo, ics_file)
        # date, title, link
        csv_content += "{:%Y-%m-%d},{},{}\n".format(promo_day, title, book_link)
        day_offset = day_offset + 1
    assert(day_offset == 7)
    with open("README.md", "a") as f:
        f.write(md_content)
    with open("lastlog_time", "r") as f:
        line = f.readline().rstrip('\n')
        lastlog_date = datetime.strptime(line, "%Y-%m-%d")
    if lastlog_date < start_thursday:
        with open("log.csv", "a") as f:
            f.write(csv_content)

if __name__ == "__main__":
    response_blog = request_with_agent("https://www.kobo.com/zh/blog")
    soup_blog = BeautifulSoup(response_blog.content, "html.parser")
    # Get the first 99 list
    for link in soup_blog.find_all("a", class_="card__link"):
        link_url = link.get("href")
        print(link_url)
    #     todo: check the date is in available
        if m := re.match(r".*99書單.*-([0-9]{1,2})-([0-9]{1,2})-([0-9]{1,2}-[0-9]{1,2})", link_url):
            print("Get the list from {}-{} to {}".format(m.group(1), m.group(2), m.group(3)))
            start_thursday = get_start_thursday(int(m.group(1)), int(m.group(2)))
            handle_list(link_url, start_thursday)
            break