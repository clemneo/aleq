from dbhelper_postgresql import DBHelper
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters
import logging
import math
from simpleeval import simple_eval
import re
import datetime
import os
import sys

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)
logger = logging.getLogger()

ADD_USER, MAIN_MENU, ADD_USER_LANDING, SEE_USERS, TIMEZONE_QN, TXN_NAME, TXN_DATE, TXN_PAYER, TXN_TOTAL, \
TXN_TAX, TXN_PAYEE_TAX_QN, TXN_PAYEE_CUSTOM_MENU, TXN_PAYEE_CUSTOM_AMOUNT, TXN_CONFIRM, \
TXN_CFM_EDIT, TXN_EDIT_TOTAL, TXN_ENDING, BALANCE_MENU, SETTLE_DEBT, HISTORY_MENU = range(20)

TOKEN = os.getenv("TOKEN")
MODE = os.getenv("MODE")

def money_parser(string):
    """Takes a string of money as accepted for input, and outputs total in cents"""
    if string[0] == '$':
        total = int(round(float(string[1:]) * 100))
    else:
        total = int(round(float(string) * 100))

    return total


def cents_to_string(amount):
    if amount < 0:
        string = "-$"
    else:
        string = "$"
    if abs(amount) < 10:
        string += '0.0' + str(abs(amount))
    elif abs(amount) < 100:
        string += '0.' + str(abs(amount))
    elif abs(amount) >= 100:
        string += str(abs(amount))[:-2] + '.' + str(abs(amount))[-2:]

    return string



def start(update, context):
    logger.info("User {} started bot".format(update.effective_user["id"]))
    context.chat_data['pending_user_list'] = []
    chat_id = update.message.chat_id
    db = DBHelper()
    user_list = db.get_users(chat_id)
    timezone_offset = db.get_timezone(chat_id)
    update.message.reply_text(str(user_list))
    if len(user_list) == 0:
        logger.info(str(user_list))
        update.message.reply_text(
            "Hello! Welcome to Alan's Equilibrium! \n" \
            "To begin, tell me your name!"
        )

        return ADD_USER
    elif len(timezone_offset) == 0:
        update.message.reply_text(
            "What is your timezone? (e.g. '+8' or '-3'"
        )
        return TIMEZONE_QN
    else:
        # Menu Code
        menu_message(update, context)
        return MAIN_MENU


def menu_message(update,context):
    custom_keyboard = [["Add Transaction"],["See/Settle Balance"],["Check History"],["Add User","See Users"],["End Session"]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    update.message.reply_text(
        "You have landed on the Menu!", reply_markup=reply_markup, quote=False
    )


def add_user_landing(update,context):
    msg = update.message.text
    reply_markup = telegram.ReplyKeyboardRemove()
    context.chat_data['pending_user_list'] = []
    update.message.reply_text("Give me the name of who you want to add.", reply_markup=reply_markup)

    return ADD_USER


def add_user(update, context):
    msg = update.message.text
    reply_markup = telegram.ReplyKeyboardRemove()
    if msg.isnumeric():
        if int(msg) < 1 or int(msg) > len(context.chat_data['pending_user_list']):
            update.message.reply_text("That number is invalid.", quote=False)
        else:
            context.chat_data['pending_user_list'].pop(int(msg)-1)
    else:
        context.chat_data['pending_user_list'].append(msg)

    reply_string = "Current list of users to be added:"
    count = 1
    for user in context.chat_data['pending_user_list']:
        reply_string += "\n" + str(count) + ") " + user
        count += 1
    reply_string += "\n\n Who else do you want to add? Give me another name, or type /confirm to add the user(s). \n" \
                    "If you have wrongly added a user, tell me their number in the list above, and I'll remove it."
    update.message.reply_text(reply_string, reply_markup=reply_markup)

    return ADD_USER


def confirm_user(update, context):
    reply_markup = telegram.ReplyKeyboardRemove()
    chat_id = update.message.chat_id
    db = DBHelper()
    added_users = []
    not_added_users = []
    reply_string = ""
    for user in context.chat_data['pending_user_list']:
        try:
            db.add_user(user, chat_id)
            added_users.append(user)
        except:
            not_added_users.append(user)
    if len(added_users) > 0:
        reply_string += "The following user(s) have been added!"
        for added_user in added_users:
            reply_string += "\n* " + added_user
    if len(not_added_users) > 0:
        reply_string += "\nThe following user(s) already exist, and have not been added"
        for not_added_user in not_added_users:
            reply_string += "\n* " + not_added_user

    update.message.reply_text(reply_string, reply_markup=reply_markup)

    reply_string2 = "What is your timezone? (e.g. '+8' or '-3')"
    #location_keyboard = telegram.KeyboardButton(text="send_location", request_location = True)
    #reply_markup2 = telegram.ReplyKeyboardMarkup([[location_keyboard]])
    update.message.reply_text(reply_string2)

    return TIMEZONE_QN

def add_timezone_with_offset(update, context):
    msg = update.message.text
    chat_id = update.message.chat_id
    offset_in_seconds = int(msg) * 3600
    db = DBHelper()
    db.set_timezone_for_group(chat_id, offset_in_seconds)

    reply_string = "Got it! I've set a UTC " + msg + " timezone for this chat!"
    reply_string += "\n\nSending you to the menu..."
    update.message.reply_text(reply_string)

    menu_message(update,context)
    return MAIN_MENU


def see_users(update, context):
    reply_markup = telegram.ReplyKeyboardRemove()
    chat_id = update.message.chat_id
    db = DBHelper()
    list_of_users = db.get_users(chat_id)
    reply_string = "Users currently in this group:"
    for user in list_of_users:
        reply_string += "\n* " + user[1]
    update.message.reply_text(reply_string, reply_markup=reply_markup)

    reply_string2 = "Type /menu to go back to the menu, or /end to terminate this session."
    reply_markup2 = telegram.ReplyKeyboardMarkup([["/menu"],["/end"]])
    update.message.reply_text(reply_string2, reply_markup=reply_markup2)

    return MAIN_MENU


def main_menu(update, context):
    menu_message(update, context)
    return MAIN_MENU


"""
>>>>>>>>>>>>>>>> ADD TRANSACTION
"""

def add_transaction_landing(update, context):
    reply_markup = telegram.ReplyKeyboardRemove()
    db = DBHelper()
    chat_id = update.message.chat_id
    user_list = db.get_users(chat_id)
    # user_id_list, name_list, balance_list = db.get_users(chat_id)
    context.chat_data['pending_transaction'] = {
        'transaction_name': '',
        'transaction_date': '',
        'transaction_payer': '',
        'transaction_total': 0,
        'transaction_tax': 1,
        'transaction_payee': {},
        'user_list':  user_list,
        'user_list_ref': [],
        'menu_list_ref': [],
        'current_payee': ''
    }
    for user in context.chat_data['pending_transaction']['user_list']:
        context.chat_data['pending_transaction']['user_list_ref'].append(user[1])
        context.chat_data['pending_transaction']['menu_list_ref'].append([user[1]])
    update.message.reply_text("What do you want to call this transaction?", reply_markup=reply_markup)

    return TXN_NAME


def add_transaction_name(update, context):
    msg = update.message.text
    context.chat_data['pending_transaction']['transaction_name'] = msg
    reply_string = "Transaction Name: " + context.chat_data['pending_transaction']['transaction_name']
    reply_string += "\n\n When did this transaction happen?"
    reply_string += "\nAccepted formats are DDMMYY, DD.MM.YY, or DD-MM-YY."
    reply_string += "Alternatively, you can press 'Today' or 'Yesterday'."
    reply_markup = telegram.ReplyKeyboardMarkup([["Today"],["Yesterday"]])
    update.message.reply_text(reply_string, reply_markup=reply_markup)

    return TXN_DATE


def add_transaction_date(update, context):
    msg = update.message.text
    chat_id = update.message.chat_id
    if len(msg) == 6:
        num = int(msg)
        year, month, day = 2000+num%100, int((num%10000-num%100)/100), num//10000
        try:
            datetime_object = datetime.datetime(year, month, day)
            date_not_valid = False
        except:
            date_not_valid = True
    elif len(msg) == 8:
        try:
            array = msg.split('-')
        except:
            array = msg.split('.')
        year, month, day = int(array[2]), int(array[1]), int(array[0])
        try:
            datetime_object = datetime.datetime(year, month, day)
            date_not_valid = False
        except:
            date_not_valid = True
    else:
        db = DBHelper()
        offset_in_seconds = db.get_timezone(chat_id)[0][0]
        current_unix_time = datetime.datetime.timestamp(update.message.date)#datetime.datetime.timestamp(datetime.datetime.now())
        if msg == "Today":
            unix_plus_offset = current_unix_time + offset_in_seconds
        elif msg == "Yesterday":
            unix_plus_offset = current_unix_time + offset_in_seconds - 86400
        datetime_object = datetime.datetime.fromtimestamp(unix_plus_offset)
        year, month, day = datetime_object.year, datetime_object.month, datetime_object.day
        date_not_valid = False

    if date_not_valid: # datetime not valid:
        reply_string = "Date not valid. Please try again."
        update.message.reply_text(reply_string)

        return TXN_DATE

    else: # datetime is valid
        context.chat_data['pending_transaction']['transaction_date'] = datetime_object
        reply_string1 = "Transaction Date: " + msg
        update.message.reply_text(reply_string1)
        reply_string2 = "Who paid for this transaction?"
        reply_markup = telegram.ReplyKeyboardMarkup(context.chat_data['pending_transaction']['menu_list_ref'])
        update.message.reply_text(
            reply_string2, reply_markup=reply_markup, quote=False
        )

        return TXN_PAYER


def add_transaction_payer(update, context):
    msg = update.message.text
    reply_string = ""
    if msg in context.chat_data['pending_transaction']['user_list_ref']:
        context.chat_data['pending_transaction']['transaction_payer'] = msg
        for user in context.chat_data['pending_transaction']['user_list_ref']:
            if msg != user:
                context.chat_data['pending_transaction']['transaction_payee'][user] = None

        reply_string += 'Transaction Payer: ' + msg
        reply_markup = telegram.ReplyKeyboardRemove()
        update.message.reply_text(
            reply_string, reply_markup=reply_markup
        )
        update.message.reply_text("How much was the total? Accepted formats are $xx, $xx.xx, xx, xx.xx")

        return TXN_TOTAL

    else:
        reply_string += "User '" + msg + "' not found. Use the buttons to make sure you tell me a user" \
                                         " that is in my database."
        reply_markup = telegram.ReplyKeyboardMarkup(context.chat_data['pending_transaction']['menu_list_ref'])
        update.message.reply_text(reply_string, reply_markup=reply_markup)

        return TXN_PAYER


def add_transaction_total(update, context):
    msg = update.message.text
    context.chat_data['pending_transaction']['transaction_total'] = money_parser(msg)
    string_amount = cents_to_string(context.chat_data['pending_transaction']['transaction_total'])
    reply_string = "The amount is " + string_amount
    update.message.reply_text(reply_string)

    reply_markup = telegram.ReplyKeyboardMarkup([["Yes","No"]])
    update.message.reply_text("Do you want to split this evenly between everyone in the group?",
                              reply_markup=reply_markup)

    return TXN_PAYEE_TAX_QN


def add_transaction_tax_landing(update, context):
    msg = update.message.text

    reply_markup = telegram.ReplyKeyboardMarkup([["1.17", "1.10"], ["1.00"]])
    update.message.reply_text("What is the tax multiplier?", reply_markup=reply_markup)

    return TXN_TAX


def transaction_custom_menu(update,context):
    msg = update.message.text
    reply_markup_array = []
    reply_string = "Current Status:"
    for key in context.chat_data['pending_transaction']['transaction_payee']:
        reply_string += "\n" + key + ": "
        if context.chat_data['pending_transaction']['transaction_payee'][key] == None:
            reply_string += "TBC"
        else:
            reply_string += cents_to_string(context.chat_data['pending_transaction']['transaction_payee'][key])
        reply_markup_array.append([key])

    reply_markup_array.append(["/confirm"])
    reply_string += "\n\nWho do you want to edit?\nPressing /confirm will split the rest of the total evenly amongst " \
                    "the rest."
    reply_markup = telegram.ReplyKeyboardMarkup(reply_markup_array)
    update.message.reply_text(reply_string, reply_markup=reply_markup, quote=False)


def add_transaction_tax(update, context):
    msg = update.message.text
    if msg == "1.00":
        pass
    else:
        context.chat_data['pending_transaction']['transaction_tax'] = float(msg)
    reply_markup = telegram.ReplyKeyboardRemove()
    reply_string = "Transaction Multiplier: " + msg + "\nI will automatically apply this multiplier to the subsequent " \
                                                      "amounts you give me."
    update.message.reply_text(reply_string, reply_markup=reply_markup)

    transaction_custom_menu(update, context)

    return TXN_PAYEE_CUSTOM_MENU


def add_transaction_custom_user(update,context):
    msg = update.message.text
    reply_string = ""
    if msg in context.chat_data['pending_transaction']['user_list_ref'] and msg != context.chat_data['pending_transaction']['transaction_payer']:
        context.chat_data['pending_transaction']['current_payee'] = msg
        reply_string += "How much did " + msg + " spend here?"
        reply_string += "\n\nMathematical operations (+), (-), (*), (/) are permitted! I will calculate the total for you."
        reply_markup = telegram.ReplyKeyboardRemove()
        update.message.reply_text(reply_string, reply_markup=reply_markup)

        return TXN_PAYEE_CUSTOM_AMOUNT

    else:
        reply_string += "Invalid user."
        update.message.reply_text(reply_string)

        return TXN_PAYEE_CUSTOM_MENU


def add_transaction_custom_amount(update, context):
    msg = update.message.text
    reply_string = ""
    try:
        msg.replace(" ","")
        raw_amount = simple_eval(msg)
        final_amount = raw_amount * context.chat_data['pending_transaction']['transaction_tax']
        final_amount_cents = math.ceil(final_amount*100)
        context.chat_data['pending_transaction']['transaction_payee'][context.chat_data['pending_transaction']['current_payee']] = final_amount_cents
        reply_string += context.chat_data['pending_transaction']['current_payee'] + " paid: " + msg + " * " + \
            str(context.chat_data['pending_transaction']['transaction_tax']) + " = " + \
            cents_to_string(final_amount_cents)
        update.message.reply_text(reply_string)
    except:
        update.message.reply_text("Something went wrong. Try again.")

    transaction_custom_menu(update,context)

    return TXN_PAYEE_CUSTOM_MENU

def add_transaction_breakeven(update,context):
    even_amount = math.ceil(context.chat_data['pending_transaction']['transaction_total'] /
                            len(context.chat_data['pending_transaction']['user_list']))
    for key in context.chat_data['pending_transaction']['transaction_payee']:
        context.chat_data['pending_transaction']['transaction_payee'][key] = even_amount


def add_transaction_confirmation(update,context):
    msg = update.message.text
    total_payee_sum = 0
    reply_string = ""
    if msg == "Yes":
        add_transaction_breakeven(update, context)
    if re.match(r'^\$\d+$|^\$\d+.\d$|^\$\d+.\d\d$|^\d+$|^\d+.\d$|^\d+.\d\d$', msg):
        context.chat_data['pending_transaction']['transaction_total'] = money_parser(msg)
    for payee in context.chat_data['pending_transaction']['transaction_payee']:
        if context.chat_data['pending_transaction']['transaction_payee'][payee] != None:
            total_payee_sum += context.chat_data['pending_transaction']['transaction_payee'][payee]
    if total_payee_sum > context.chat_data['pending_transaction']['transaction_total']:
        reply_string += "The payee sum is more than the transaction total. Check again."
        reply_markup = telegram.ReplyKeyboardMarkup([["Edit Total"],["Edit Payees"],["Cancel Transaction"]])
        update.message.reply_text(reply_string, reply_markup=reply_markup)

        return TXN_CFM_EDIT
    else:
        split_no = 1
        current_amount = 0
        for payee in context.chat_data['pending_transaction']['transaction_payee']:
            if context.chat_data['pending_transaction']['transaction_payee'][payee] == None:
                split_no += 1
            else:
                current_amount += context.chat_data['pending_transaction']['transaction_payee'][payee]

        split_amount = math.ceil((context.chat_data['pending_transaction']['transaction_total'] - current_amount)/split_no)
        for payee in context.chat_data['pending_transaction']['transaction_payee']:
            if context.chat_data['pending_transaction']['transaction_payee'][payee] == None:
                context.chat_data['pending_transaction']['transaction_payee'][payee] = split_amount

        final_overview(update, context)

        return TXN_ENDING

def cancel_transaction(update,context):
    reply_string = "Cancelling transaction... Returning to the main menu"
    reply_markup = telegram.ReplyKeyboardRemove()
    update.message.reply_text(reply_string, reply_markup=reply_markup)
    menu_message(update,context)
    return MAIN_MENU

def final_overview(update, context):
    reply_string = ""
    reply_string += "Name: " + context.chat_data['pending_transaction']['transaction_name']
    reply_string += "\nDate: " + context.chat_data['pending_transaction']['transaction_date'].strftime('%d/%m/%Y')
    reply_string += "\nTotal: " + cents_to_string(context.chat_data['pending_transaction']['transaction_total'])
    reply_string += "\n\n" + context.chat_data['pending_transaction']['transaction_payer'] + " paid for this transaction."
    for payee in context.chat_data['pending_transaction']['transaction_payee']:
        reply_string += "\n" + payee + " spent "
        reply_string += cents_to_string(context.chat_data['pending_transaction']['transaction_payee'][payee]) + "."
    reply_markup = telegram.ReplyKeyboardMarkup([["/confirm"], ["/cancel"]])
    update.message.reply_text(reply_string, reply_markup=reply_markup)



def transaction_custom_menu_edit(update, context):
    transaction_custom_menu(update, context)
    return TXN_PAYEE_CUSTOM_MENU


def add_transaction_edit_total(update,context):
    update.message.reply_text("How much was the total? Accepted formats are $xx, $xx.xx, xx, xx.xx")

    return TXN_EDIT_TOTAL

def transaction_commit(update, context):
    db = DBHelper()
    chat_id = update.message.chat_id
    name = context.chat_data['pending_transaction']['transaction_name']
    date = context.chat_data['pending_transaction']['transaction_date'].timestamp()
    type = 0
    total = context.chat_data['pending_transaction']['transaction_total']
    payer_id = db.get_user_id(chat_id, context.chat_data['pending_transaction']['transaction_payer'])
    payees = context.chat_data['pending_transaction']['transaction_payee']
    payee_id_dict = {}
    for payee in payees:
        payee_id_dict[db.get_user_id(chat_id,payee)] = payees[payee]
    db.add_event(chat_id, name, date, type, total, payer_id, payee_id_dict)
    db.clear_ps_by_group(chat_id)

    reply_string = "Transaction added! Type /menu to return to the menu, or /end to terminate the session."
    reply_markup = telegram.ReplyKeyboardMarkup([["/menu"],["/end"]])
    update.message.reply_text(reply_string, reply_markup=reply_markup)

    return MAIN_MENU

"""
>>>>>>>>>>>>>>>> BALANCE
"""

def balance_menu(update, context):
    # say something about their current balance
    db = DBHelper()
    chat_id = update.message.chat_id
    balance_dict = db.get_balances(chat_id)
    context.chat_data['balance_menu'] = {
        'username_dict': "",
        'user_list': []
    }


    reply_string = "*Current Balances*"
    reply_markup = telegram.ReplyKeyboardRemove()
    not_in_equilibrium = False

    for user_id in balance_dict:
        reply_string += "\n" + balance_dict[user_id][0] + ": " + cents_to_string(balance_dict[user_id][1])
        if balance_dict[user_id][1] != 0:
            not_in_equilibrium = True
    reply_string = reply_string.replace(".", "\.")
    reply_string = reply_string.replace("-", "\-")
    update.message.reply_text(reply_string, reply_markup=reply_markup, parse_mode="MarkdownV2")

    if not_in_equilibrium:
        ps_dict = db.get_ps(chat_id)
        if len(ps_dict) == 0:
            total_list = []
            for user_id in balance_dict:
                total_list.append([balance_dict[user_id][1], user_id])
            # this gives you [[balance, user_id], [balance, user_id], ...]
            undone = True
            while undone: # this condition should be something about when all balance
                total_list.sort()
                if abs(total_list[0][0]) > total_list[-1][0]:
                    if total_list[-1][1] not in ps_dict:
                        ps_dict[total_list[-1][1]] = [(total_list[0][1], total_list[-1][0])]
                    else:
                        ps_dict[total_list[-1][1]].append((total_list[0][1], total_list[-1][0]))
                    total_list[0][0] += total_list[-1][0]
                    total_list[-1][0] = 0
                else:
                    if total_list[-1][1] not in ps_dict:
                        ps_dict[total_list[-1][1]] = [(total_list[0][1], abs(total_list[0][0]))]
                    else:
                        ps_dict[total_list[-1][1]].append((total_list[0][1], abs(total_list[0][0])))
                    total_list[-1][0] += total_list[0][0]
                    total_list[0][0] = 0
                undone = False
                for user in total_list:
                    if user[0] != 0:
                        undone = True
            for sender_id in ps_dict:
                for receiver_tuple in ps_dict[sender_id]:
                    db.add_ps(chat_id, sender_id, receiver_tuple[0], receiver_tuple[1])

        ps_dict = db.get_ps(chat_id)
        username_dict = db.get_id_to_username_dict(chat_id)
        reply_string2 = "To settle debts:"
        for user_id in ps_dict:
            count = 0
            reply_string2 += "\n" + username_dict[user_id] + ": "
            for receiver_tuple in ps_dict[user_id]:
                if count > 0:
                    reply_string2 += ", "
                reply_string2 += "Give " + cents_to_string(receiver_tuple[1]) + " to " + username_dict[receiver_tuple[0]]
                count += 1

        reply_string2 += "\n\nType /settle to confirm you've paid, or /menu to go back to the menu."
        reply_markup = telegram.ReplyKeyboardMarkup([["/settle"],["/menu"]])
        update.message.reply_text(reply_string2, reply_markup=reply_markup, quote=False)
    else:
        reply_string2 = "You are in equilibrium! Type /menu to go back to the main menu, or /end to terminate session."
        reply_markup = telegram.ReplyKeyboardMarkup([["/menu"],["/end"]])
        update.message.reply_text(reply_string2, quote=False)


    return BALANCE_MENU

def settle_debt_menu(update, context):
    reply_string = "Who has paid off their debt?"
    chat_id = update.message.chat_id
    db = DBHelper()
    ps_dict = db.get_ps(chat_id)
    username_dict = db.get_id_to_username_dict(chat_id)
    user_list = []
    for user_id in ps_dict:
        user_list.append([username_dict[user_id]])
        context.chat_data["balance_menu"]["user_list"].append(username_dict[user_id])
    #context.chat_data["balance_menu"]['user_list'] = user_list
    reply_markup = telegram.ReplyKeyboardMarkup(user_list)

    update.message.reply_text(reply_string, reply_markup=reply_markup)

    return SETTLE_DEBT

def settle_debt_function(update,context):
    msg = update.message.text
    chat_id = update.message.chat_id
    if msg not in context.chat_data["balance_menu"]['user_list']:
        reply_string = "User '" + msg + "' is not in the list. Use the buttons to make sure you tell me a user" \
                                         " that is in the list."
        update.message.reply_text(reply_string)

    else:
        db = DBHelper()
        sender_id = db.get_user_id(chat_id, msg)
        ps_dict = db.get_ps(chat_id)
        # add the events
        name = "Settlement by " + msg
        date = datetime.datetime.timestamp(datetime.datetime.now())
        type = 1
        total = 0
        receivers = {}
        for receiver_tuple in ps_dict[sender_id]:
            total += receiver_tuple[1]
            receivers[receiver_tuple[0]] = receiver_tuple[1]

        db.add_event(chat_id, name, date, 1, total, sender_id, receivers)
        # remove the pending settlements
        db.clear_ps_by_group(chat_id)

        balance_menu(update, context)

    return BALANCE_MENU

def generate_history(update, context):
    db = DBHelper()
    chat_id = update.message.chat_id
    outstanding_txns = db.get_outstanding_txn(chat_id)
    username_dict = db.get_id_to_username_dict(chat_id)
    context.chat_data['history_menu'] = {
        'menu_ids': {}
    }

    if len(outstanding_txns) != 0:
        id_count = 1
        reply_string = "Transactions contributing to the current outstanding balances:"
        for event_id in outstanding_txns:
            if event_id not in context.chat_data['history_menu']['menu_ids'].values():
                context.chat_data['history_menu']['menu_ids'][id_count] = event_id
                id_count += 1

        for number in context.chat_data['history_menu']['menu_ids']:
            event_tuple = db.get_event_by_id(context.chat_data['history_menu']['menu_ids'][number])
            dt = datetime.datetime.fromtimestamp(event_tuple[1])
            dt_string = dt.strftime('%d/%m/%Y')
            reply_string += "\n" + str(number) + ". " + dt_string + " - " + event_tuple[0] + " (" + \
                            cents_to_string(event_tuple[3]) + ")"

        reply_string += "\n\nTell me the number of the event if you want to see more."
        update.message.reply_text(reply_string)

        reply_string2 = "If you would like to see the past ten transactions instead, press /last10"
        reply_string2 += "\nIf not, press /menu to go back to the main menu, or /end to terminate this session."
        reply_markup = telegram.ReplyKeyboardMarkup([["/last10"],["/menu"],["/end"]])
        update.message.reply_text(reply_string2, reply_markup=reply_markup, quote=False)

        return HISTORY_MENU
        # landing: Current transactions contributing to the outstanding balances:
        # 1. DATE NAME
        # 2. DATE NAME
        # menu_id: {1: event_id}

    else:
        reply_string = "You are in equilibrium! Nobody owes each other money."
        reply_markup = telegram.ReplyKeyboardRemove()
        update.message.reply_text(reply_string, reply_markup=reply_markup)
        generate_last_ten_events(update,context)

def generate_last_ten_events(update,context):
    db = DBHelper()
    chat_id = update.message.chat_id
    ten_events_list = db.get_ten_events_by_chat_id(chat_id)
    index = 1
    reply_string = "Showing the last ten events...\n"
    context.chat_data['history_menu'] = {
        'menu_ids': {}
    }
    for event in ten_events_list:
        context.chat_data['history_menu']['menu_ids'][index] = event[0]
        dt = datetime.datetime.fromtimestamp(event[2])
        dt_string = dt.strftime('%d/%m/%Y')
        reply_string += "\n" + str(index) + ". " + dt_string + " - " + event[1] + " (" + \
                        cents_to_string(event[5]) + ")"
        index += 1

    reply_string += "\n\nTell me the number of the event if you want to see more."
    update.message.reply_text(reply_string)

    reply_string2 = "Alternatively, press /menu to go back to the main menu, or /end to terminate this session."
    reply_markup = telegram.ReplyKeyboardMarkup([["/menu"], ["/end"]])
    update.message.reply_text(reply_string2, reply_markup=reply_markup, quote=False)

    return HISTORY_MENU

def see_event(update, context):
    msg = update.message.text
    chat_id = update.message.chat_id
    if int(msg) not in context.chat_data['history_menu']['menu_ids']:
        reply_string = "Invalid number. Try again."
        update.message.reply_text(reply_string)
    else:
        db = DBHelper()
        username_dict = db.get_id_to_username_dict(chat_id)
        event_id = context.chat_data['history_menu']['menu_ids'][int(msg)]
        event_data = db.get_event_by_id(event_id)
        reply_string = "Showing <Item " + msg + ">..."
        reply_string += "\nName: " + event_data[0]
        dt = datetime.datetime.fromtimestamp(event[1])
        dt_string = dt.strftime('%d/%m/%Y')
        reply_string += "\nDate: " + dt_string
        if event_data[2] == 0: # if its a purchase
            reply_string += "\nTotal: " + cents_to_string(event_data[3])
            txn_list = db.get_txns_by_event_id(event_id)
            payer_id = txn_list[0][0]
            reply_string += "\n\n" + username_dict[payer_id] + " paid for this."
            for txn in txn_list:
                reply_string += "\n" + username_dict[txn[1]] + " spent " + cents_to_string(txn[2]) + "."

            update.message.reply_text(reply_string)

        else: # if its a settlement
            txn = db.get_txns_by_event_id(event_id)[0]
            reply_string += "\n\n" + username_dict[txn[0]] + " repaid " + cents_to_string(txn[2]) + " to " + username_dict[txn[1]]

            update.message.reply_text(reply_string)

        reply_string2 = "Give me another number to see another transaction."
        reply_string2 += "\nAlternatively, press /menu to go back to the main menu, or /end to terminate this session."
        update.message.reply_text(reply_string2, quote=False)

def end(update, context):
    reply_markup = telegram.ReplyKeyboardRemove()
    update.message.reply_text(
        'Terminating session... Type /start or /menu to bring me back online!', reply_markup=reply_markup
    )
    return ConversationHandler.END


def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    db = DBHelper()
    db.setup()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start',start),
            CommandHandler('menu', main_menu)],
        states={
            MAIN_MENU: [
                CommandHandler('menu', main_menu),
                MessageHandler(Filters.regex('Add User'), add_user_landing),
                MessageHandler(Filters.regex('See Users'), see_users),
                MessageHandler(Filters.regex('Add Transaction'),add_transaction_landing),
                MessageHandler(Filters.regex('^See/Settle Balance$'), balance_menu),
                MessageHandler(Filters.regex('Check History'), generate_history),
                MessageHandler(Filters.regex('End Session'), end)
            ],
            ADD_USER_LANDING: [
                MessageHandler(Filters.text & (~Filters.command), add_user),
            ],
            ADD_USER: [
                CommandHandler('confirm', confirm_user),
                MessageHandler(Filters.text & (~Filters.command), add_user)
            ],
            TIMEZONE_QN: [
                MessageHandler(Filters.regex('^[-|+]([0-9]|[1][0-2])$'), add_timezone_with_offset)
            ],
            SEE_USERS: [
                CommandHandler('menu',main_menu),
            ],
            TXN_NAME: [
                MessageHandler(Filters.text & (~Filters.command), add_transaction_name)
            ],
            TXN_DATE: [
                MessageHandler(Filters.regex('^\d\d\d\d\d\d$|^\d\d[-|.]\d\d[-|.]\d\d$|^Today$|^Yesterday$'), add_transaction_date)
            ],
            TXN_PAYER: [
                MessageHandler(Filters.text & (~Filters.command), add_transaction_payer)
            ],
            TXN_TOTAL: [
                MessageHandler(Filters.regex('^\$\d+$|^\$\d+.\d$|^\$\d+.\d\d$|^\d+$|^\d+.\d$|^\d+.\d\d$'),
                               add_transaction_total)
            ],
            TXN_PAYEE_TAX_QN: [
                MessageHandler(Filters.regex('^No$'), add_transaction_tax_landing),
                MessageHandler(Filters.regex('^Yes$'), add_transaction_confirmation)
            ],
            TXN_TAX: [
                MessageHandler(Filters.regex('^1\.\d\d?$'), add_transaction_tax)
            ],
            TXN_PAYEE_CUSTOM_MENU: [
                CommandHandler('confirm', add_transaction_confirmation),
                MessageHandler(Filters.text & (~Filters.command), add_transaction_custom_user)

            ],
            TXN_PAYEE_CUSTOM_AMOUNT: [
                MessageHandler(Filters.regex('^[0-9\+\-\*\/\.\ ]*$'),
                               add_transaction_custom_amount)
            ],
            TXN_CFM_EDIT: [
                MessageHandler(Filters.regex('Edit Total'),
                               add_transaction_edit_total),
                MessageHandler(Filters.regex('Edit Payees'),
                                transaction_custom_menu_edit),
                MessageHandler(Filters.regex('Cancel Transaction'),
                               cancel_transaction),
                CommandHandler('cancel', end)
            ],
            TXN_EDIT_TOTAL: [
                MessageHandler(Filters.regex('^\$\d+$|^\$\d+.\d$|^\$\d+.\d\d$|^\d+$|^\d+.\d$|^\d+.\d\d$'),
                               add_transaction_confirmation)
            ],
            TXN_ENDING: [
                CommandHandler('cancel', end),
                CommandHandler('confirm', transaction_commit)
            ],
            BALANCE_MENU: [
                CommandHandler('settle', settle_debt_menu),
                CommandHandler('menu', main_menu)
            ],
            SETTLE_DEBT: [
                CommandHandler('cancel', balance_menu),
                MessageHandler(Filters.text & (~Filters.command), settle_debt_function)
            ],
            HISTORY_MENU: [
                CommandHandler('last10', generate_last_ten_events),
                CommandHandler('menu', main_menu),
                MessageHandler(Filters.regex('^[0-9]*$'), see_event)
            ]
        },
        fallbacks=[CommandHandler('end',end)],
        per_user=False,
        conversation_timeout=300.0
    )

    dispatcher.add_handler(conv_handler)

    # Start the Bot
    if MODE == "dev":
        updater.start_polling()

    elif MODE == "prod":
        PORT = int(os.environ.get('PORT',8443))
        updater.start_webhook(listen='0.0.0.0',
                              port=int(PORT),
                              url_path=TOKEN,
                              webhook_url="https://powerful-sierra-80016.herokuapp.com/" + TOKEN)
    else:
        logger.error("No MODE specified... Remember to define MODE as 'dev' or 'prod' in your environment variables!")
        sys.exit(1)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()