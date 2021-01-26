from gevent import monkey
monkey.patch_all()
# then import this
import datetime
import logging
import re
import playwright.helper
from bs4 import BeautifulSoup
from playwright import sync_playwright
from pydantic import BaseSettings, SecretStr
from telegram.ext import (CallbackContext, CommandHandler,
                          Updater, PicklePersistence)
from telegram import Update



# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

EMAIL_REGEXP = re.compile('^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$')

class Settings(BaseSettings):
    TOKEN: SecretStr

    class Config:
        env_prefix = "UDI_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def main():
    config = Settings()
    my_persistence = PicklePersistence(filename='bot_status.db')
    updater = Updater(config.TOKEN.get_secret_value(),
                      use_context=True, persistence=my_persistence)

    # Get the dispatcher to register handlers
    # with sync_playwright() as p:
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("set_username", set_username))
    dp.add_handler(CommandHandler("set_password", set_password))
    #dp.add_handler(CommandHandler("check", check_wrapper(p)))
    dp.add_handler(CommandHandler("check", check))
    updater.start_polling()
    updater.idle()


def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    logger.info("{}: start".format(chat_id))
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        'Hi! Set up your UDI username and password with /set_username and /set_password commands. \
        Then fire /check and the bot will find out if it\'s possible to get the appoinment earlier.')


def set_username(update: Update, context:  CallbackContext):
    chat_id = update.message.chat_id
    try:
        username = str(context.args[0])
        if not is_valid_username(username):
            update.message.reply_text(
                'invalid username {}\n '.format(username))
            return
        context.user_data.update({"username": username})
        update.message.reply_text("username is set to {}".format(
            context.user_data.get("username")))
        logger.info("{}: set_username: {}".format(
            chat_id, username))
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set_username <username>')


def set_password(update: Update, context:  CallbackContext):
    chat_id = update.message.chat_id
    try:

        password = str(context.args[0])
        if not is_valid_password(password):
            update.message.reply_text(
                'invalid passowrd')
            return
        context.user_data.update({"password": password})
        update.message.reply_text("password is set")
        logger.info("{}: set_username: SET".format(chat_id))
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set_password <password>')
        logger.info("{}: set_username: NOT SET")


def valid_context(context: CallbackContext) -> bool:
    p = context.user_data.get("password")
    u = context.user_data.get("username")

    if is_valid_username(u) & is_valid_password(p):
        return True
    return False


def is_valid_username(u: str) -> bool:
    if u is None:
        return False
    if EMAIL_REGEXP.search(u):
        return True
    return False


def is_valid_password(p: str) -> bool:
    if p is None:
        return False
    if len(p) != 0:
        return True
    return False


# def check_wrapper():
def check(update: Update, context: CallbackContext):
    if not valid_context(context):
        update.message.reply_text(
            'Usage: please set username and password first')
        return
    print("checking UDI for {}".format(context.user_data.get("username")))
    check_udi(update, context)
# return check


playwright = sync_playwright().start()
browser = playwright.chromium.launch()


def check_udi(update: Update, context:  CallbackContext):
    my_browser = browser.newContext()
    page = my_browser.newPage()
    update.message.reply_text("Started checking the UDI's availability")
    try:
        page.goto("https://my.udi.no")
        page.waitForSelector(
            selector="#api > div > div.entry > div:nth-child(1) > label", timeout=10000)
    except Exception as exc:
        logger.error(exc)
        update.message.reply_text("Unable to reach udi.no. Try again later")
        return
    try:
        page.type("#logonIdentifier", context.user_data.get("username"))
        page.type("#password", context.user_data.get("password"))

        # page.screenshot(path="screenshot_1_login.png")
        page.click("#next")

        go_to_application_btn = "#root > div > div:nth-child(9) > div > div > div.ApplicationList__table-wrapper___1g7-a > table > tbody > tr > td.ApplicationList__white-space-nowrap___1g7-a > a"
        page.waitForSelector(go_to_application_btn)
    except Exception as exc:
        logger.error(exc)
        update.message.reply_text("Unable to login. Check credentials")
        return
    try:
        # page.screenshot(path="screenshot_2_applicationlist.png")
        page.click(go_to_application_btn)
        change_appointment_btn = "#root > div > main > div > div > div > div:nth-child(5) > div:nth-child(1) > div.book > div > button"
        page.waitForSelector(
            change_appointment_btn)
        # page.screenshot(path="screenshot_3_application.png")
        booked_date_text = page.textContent(
            "#root > div > main > div > div > div > div:nth-child(5) > div:nth-child(1) > div.box.mb-1 > div > div > h3")
        booked_date = datetime.datetime.strptime(
            booked_date_text, '%A %B %d, %Y')
        booked_time_text = page.textContent(
            "#root > div > main > div > div > div > div:nth-child(5) > div:nth-child(1) > div.box.mb-1 > div > div > p")
        print("Existing booking found: {} {}".format(
            booked_time_text, booked_date_text))
        print("Existing booking parsed date: {}".format(
            booked_date))
        update.message.reply_text("I found your exsisting appointment: {} {}\nChecking if I can find an earlier time slot".format(
            booked_time_text, booked_date_text))
    except Exception as exc:
        logger.error(exc)
        update.message.reply_text(
            "Unable to find the appointment. Have you booked one?")
        return
    page.click(change_appointment_btn)

    for i in range(12):
        try:
            cancel_appointment_change_btn = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_btnCancel"
            page.waitForSelector(cancel_appointment_change_btn)
            month_text = page.textContent(
                "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_pnlCalendarTop > div > div.col-xs-12.col-sm-pull-4.col-sm-4.p-x-0.month.text-xs-center > h2")
            month = datetime.datetime.strptime(month_text, '%B %Y')
            # page.screenshot(
            #    path="screenshot_4_selectdate_{}.png".format(month))
            print("Current page month: {}".format(month))
            calendar_table_slct = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_ccCalendar > tbody"

            calendar_table_t = page.innerHTML(calendar_table_slct)
            table_data = [[cell.text for cell in row("td")]
                          for row in BeautifulSoup(calendar_table_t, features="html.parser")("tr")]

            available_day = find_available(table_data)
            if available_day != 0:
                first_available_date = month.replace(day=available_day)
                if first_available_date < booked_date:
                    print("FIRST AVAILABLE IS EARLIER THAN THE BOOKED DATE: {}".format(
                        first_available_date))
                    update.message.reply_text(
                        "I found a time slot {} which is earlier than the one you have! Go to https://my.udi.no and book it first!".format(first_available_date))
                else:
                    print("FIRST AVAILABLE: {}".format(first_available_date))
                    update.message.reply_text(
                        "I couldn't find any earlier time slot :( The earliest now is {}. Come back next time!".format(first_available_date))
                break
            next_month_btn = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_btnNext"
            page.click(next_month_btn)
        except Exception as exc:
            logger.error(exc)
            update.message.reply_text(
                "I couldn't get the UDI's calendar. Please try again later")
            return


not_available_re = re.compile(
    r"\d{1,2}(No available appointments)?\s?$|^$")

first_digits_re = re.compile(r"(\d{1,2}).*")


def is_available_date(s: str) -> bool:
    return not not_available_re.match(s)


def find_available(table: list) -> int:
    for week in table:
        for day in week:
            if is_available_date(day):
                m = first_digits_re.match(day)
                if m.group(1) is not None:
                    return int(m.group(1))
    return 0


if __name__ == "__main__":
    main()
