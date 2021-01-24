import datetime
import logging
import re
import tempfile

import playwright.helper
from bs4 import BeautifulSoup
from playwright import sync_playwright
from pydantic import BaseSettings, SecretStr
from telegram.ext import (CallbackContext, CommandHandler, Filters,
                          MessageHandler, Updater)
from telegram import Update


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

EMAIL_REGEXP = re.compile('^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$')


class Settings(BaseSettings):
    EMAIL: str
    PWD: SecretStr
    TOKEN: SecretStr

    class Config:
        env_prefix = "UDI_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def main():
    config = Settings()

    updater = Updater(config.TOKEN.get_secret_value(), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("set_username", set_username))
    dp.add_handler(CommandHandler("set_password", set_password))
    dp.add_handler(CommandHandler("check", check))

    updater.start_polling()

    updater.idle()


def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    logger.info("{}: start".format(chat_id))
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        'Hi! set your UDI username and password with /set_username  and /set_password commands')


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
    if EMAIL_REGEXP.search(u):
        return True
    return False


def is_valid_password(p: str) -> bool:
    if len(p) != 0:
        return True
    return False


def check(update: Update, context: CallbackContext):
    print("checking UDI for {}".format(context.user_data.get("username")))
    check_udi(context)


def check_udi(context:  CallbackContext):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.newPage()
        # page.goto("https://selfservice.udi.no/en-gb/")
        page.goto("https://my.udi.no")
        page.waitForSelector(
            selector="#api > div > div.entry > div:nth-child(1) > label", timeout=10000)
        # page.type("#logonIdentifier", config.EMAIL)
        page.type("#logonIdentifier", context.user_data.get("username"))

        # page.type("#password", config.PWD.get_secret_value())
        page.type("#logonIdentifier", context.user_data.get("password"))
        page.screenshot(path="screenshot_1_login.png")
        page.click("#next")
        go_to_application_btn = "#root > div > div:nth-child(9) > div > div > div.ApplicationList__table-wrapper___1g7-a > table > tbody > tr > td.ApplicationList__white-space-nowrap___1g7-a > a"
        page.waitForSelector(go_to_application_btn)
        page.screenshot(path="screenshot_2_applicationlist.png")

        page.click(go_to_application_btn)

        change_appointment_btn = "#root > div > main > div > div > div > div:nth-child(5) > div:nth-child(1) > div.book > div > button"
        page.waitForSelector(
            change_appointment_btn)
        page.screenshot(path="screenshot_3_application.png")

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

        page.click(change_appointment_btn)

        for i in range(12):
            cancel_appointment_change_btn = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_btnCancel"
            page.waitForSelector(cancel_appointment_change_btn)

            month_text = page.textContent(
                "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_pnlCalendarTop > div > div.col-xs-12.col-sm-pull-4.col-sm-4.p-x-0.month.text-xs-center > h2")
            month = datetime.datetime.strptime(month_text, '%B %Y')
            page.screenshot(
                path="screenshot_4_selectdate_{}.png".format(month))

            print("Current page month: {}".format(month))

            calendar_table_slct = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_ccCalendar > tbody"

            # calendar_table = page.textContent(calendar_table_slct)
            calendar_table_t = page.innerHTML(calendar_table_slct)
            table_data = [[cell.text for cell in row("td")]
                          for row in BeautifulSoup(calendar_table_t, features="html.parser")("tr")]
            # print("Calendar table for {}: {}\n".format(month, calendar_table))

            # print("Calendar innerHTML for {}: {}\n".format(
            #    month, calendar_table_t))

            # print("Calendar bs for {}: {}".format(month, table_data))

            available_day = find_available(table_data)
            if available_day != 0:
                first_available_date = month.replace(day=available_day)

                if first_available_date < booked_date:
                    print("FIRST AVAILABLE IS SOONER THAN BOOKED DATE: {}".format(
                        first_available_date))
                else:
                    print("FIRST AVAILABLE: {}".format(first_available_date))
                break

            next_month_btn = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_btnNext"
            page.click(next_month_btn)


# available_re = re.compile("\d{1,2}Available appointments")
not_available_re = re.compile(
    r"\d{1,2}(No available appointments)?\s?$|^$")

first_digits_re = re.compile(r"(\d{1,2}).*")


def is_available_date(s: str) -> bool:
    # if len(s) == 0:
    #    return False

    return not not_available_re.match(s)


def find_available(table: list) -> int:
    for week in table:
        for day in week:
            # print("{} IS  available".format(day) if is_available_date(
            #    day) else "{} is NOT available".format(day))
            if is_available_date(day):
                m = first_digits_re.match(day)
                if m.group(1) is not None:
                    return int(m.group(1))
    return 0

    # page.click("#ctl00_BodyRegion_PageRegion_MainRegion_LogInHeading")
    #
    # page.type("input[type=email]", config.EMAIL)
    # page.type("input[type=password]", config.PWD.get_secret_value())
    # page.click("#next")
    #
    # try:
    #    book_btn_id: str = "#ctl00_BodyRegion_PageRegion_MainRegion_IconNavigationTile2_heading"
    #    page.waitForSelector(book_btn_id)
    #    page.click(book_btn_id)
    # except playwright.helper.TimeoutError:
    #    msg = "Failed to login. Check your password."
    #    print(msg)
    #    telegram_send.send(messages=[msg])
    #    return
    #
    # click on the first one in the list
    # page.click(
    #    "#ctl00_BodyRegion_PageRegion_MainRegion_ApplicationOverview_applicationOverviewListView_ctrl0_btnBookAppointment"
    # )
    #
    # try:
    #    page.waitForSelector(
    #        "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_divErrorMessageForNoAvailabelAppointments",
    #        timeout=5000,
    #    )
    #    print("No appointments")
    #    return
    # except playwright.helper.TimeoutError:
    #    msg = "Looks like UDI is ready for appointments"
    #    telegram_send.send(messages=[msg])
    #
    #    with tempfile.TemporaryFile("r+b") as fp:
    #        encoded_img = page.screenshot(type="png")
    #        fp.write(encoded_img)
    #        fp.seek(0, 0)
    #        telegram_send.send(images=[fp])


if __name__ == "__main__":
    main()
