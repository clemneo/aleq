import os
import psycopg2
import pandas as pd

class DBHelper:
    def __init__(self):
        DATABASE_URL = os.environ['DATABASE_URL']
        self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')

        def setup(self):
            stmt1 = "CREATE TABLE IF NOT EXISTS users (" \
                    "user_id serial NOT NULL PRIMARY KEY, " \
                    "name TEXT NOT NULL, " \
                    "balance integer NOT NULL, " \
                    "group_id integer NOT NULL," \
                    "UNIQUE(group_id, name)" \
                    ")"
            stmt2 = "CREATE TABLE IF NOT EXISTS event (" \
                    "event_id serial NOT NULL PRIMARY KEY, " \
                    "name TEXT NOT NULL, " \
                    "date integer NOT NULL, " \
                    "type integer NOT NULL, " \
                    "group_id integer NOT NULL," \
                    "total integer NOT NULL)"
            # type 0 transaction 1 repayment
            stmt3 = "CREATE TABLE IF NOT EXISTS txn (" \
                    "txn_id serial NOT NULL PRIMARY KEY, " \
                    "event_id integer NOT NULL," \
                    "payer_id integer NOT NULL, " \
                    "debtor_id integer NOT NULL, " \
                    "amount integer NOT NULL, " \
                    "group_id integer NOT NULL, " \
                    "settled_status integer NOT NULL," \
                    "FOREIGN KEY (payer_id) REFERENCES users (user_id)," \
                    "FOREIGN KEY (debtor_id) REFERENCES users (user_id))"
            stmt4 = "CREATE TABLE IF NOT EXISTS pending_settlements (" \
                    "ps_id serial NOT NULL PRIMARY KEY," \
                    "group_id integer NOT NULL," \
                    "sender_id integer NOT NULL," \
                    "receiver_id integer NOT NULL," \
                    "amount integer NOT NULL," \
                    "FOREIGN KEY (sender_id) REFERENCES users (user_id)," \
                    "FOREIGN KEY (receiver_id) REFERENCES users (user_id))"
            stmt5 = "CREATE TABLE IF NOT EXISTS timezone_offset (" \
                    "group_id integer NOT NULL," \
                    "offset_in_seconds integer NOT NULL," \
                    "UNIQUE(group_id))"
            cursor = self.conn.cursor()
            cursor.execute(stmt1)
            cursor.execute(stmt2)
            cursor.execute(stmt3)
            cursor.execute(stmt4)
            cursor.execute(stmt5)
            self.conn.commit()
            cursor.close()

        def get_users(self, group_id):
            """tuple list: Returns (x,y,z) where x[n] gives you user_id, y[n] gives you name, z[n] gives you balance"""
            """total list: Returns [(user_id1,username1,balance1),(user_id2,username2,balance2)...]"""
            stmt = "SELECT user_id, name, balance FROM users WHERE group_id = %s"
            args = (group_id,)
            cursor = self.conn.cursor()
            total_list = []
            try:
                cursor.execute(stmt, args)
                for record in cursor:
                    total_list.append(record)
                # total_list = cursor.fetchall()
            except:
                print("returning empty list")
            # user_id_list = [x[0] for x in total_list]
            # name_list = [x[1] for x in total_list]
            # balance_list = [x[2] for x in total_list]
            # return (user_id_list, name_list, balance_list)
            cursor.close()
            return total_list

        def get_id_to_username_dict(self, group_id):
            stmt = "SELECT user_id, name FROM users WHERE group_id = %s"
            args = (group_id,)
            cursor = self.conn.cursor()
            id_name_dict = {}
            cursor.execute(stmt, args)
            try:
                for row in cursor:
                    id_name_dict[row[0]] = row[1]
            except TypeError:
                print("No User Found in group_id")
                pass

            cursor.close()
            return id_name_dict

        def add_user(self, name, group_id):
            """Adds a user given a name (string) and group_id (int)"""
            stmt = "INSERT INTO users (name, group_id,balance) VALUES (%s,%s,0)"
            args = (name, group_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

        def remove_user(self, user_id):
            """Removes a user, but technically just sets the group_id to 0"""
            stmt = "UPDATE users SET group_id = 0 WHERE user_id = %s"
            args = (user_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

        def get_user_id(self, chat_id, name):
            stmt = "SELECT user_id FROM users WHERE group_id = %s AND name = %s"
            args = (chat_id, name)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            user_id = cursor.fetchone()[0]
            cursor.close()
            return user_id

        def set_timezone_for_group(self, chat_id, offset):
            stmt = "INSERT INTO timezone_offset (group_id, offset_in_seconds) VALUES (%s,%s)"
            args = (chat_id, offset)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

        def get_timezone(self, chat_id):
            stmt = "SELECT offset_in_seconds FROM timezone_offset WHERE group_id = %s"
            args = (chat_id,)
            cursor = self.conn.cursor()
            try:
                cursor.execute(stmt, args)
                object = cursor.fetchall()
            except:
                object = []

            cursor.close()
            # [(seconds_offset, )]
            return object

        def add_event(self, chat_id, name, date, type, total, payer_id, payees):
            stmt = "INSERT INTO event (name, date, type, group_id, total) VALUES (%s,%s,%s,%s,%s) RETURNING event_id"
            args = (name, date, type, chat_id, total)

            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            event_id = cursor.fetchone()[0]
            total_owed = 0

            for debtor_id in payees:
                stmt = "INSERT INTO txn (event_id, payer_id, debtor_id, amount, group_id, settled_status)" + \
                       " VALUES (%s,%s,%s,%s,%s,%s)"
                args = (event_id, payer_id, debtor_id, payees[debtor_id], chat_id, 0)
                cursor.execute(stmt, args)

                stmt2 = "UPDATE users SET balance = balance + %s WHERE user_id = %s"
                args2 = (payees[debtor_id], debtor_id)
                cursor.execute(stmt2, args2)

                total_owed += payees[debtor_id]

            stmt3 = "UPDATE users SET balance = balance - %s WHERE user_id = %s"
            args3 = (total_owed, payer_id)
            cursor.execute(stmt3, args3)
            self.conn.commit()

            # todo: test repayments settled status update below
            if type == 1:
                stmt4 = "SELECT balance FROM users WHERE group_id = %s"
                args4 = (chat_id,)
                balances = [x[0] for x in self.conn.execute(stmt4, args4)]
                if all(b == 0 for b in balances):
                    stmt5 = "UPDATE txn SET settled_status = 1 WHERE group_id = %s AND settled_status = 0"
                    args5 = (chat_id,)
                    cursor.execute(stmt5, args5)
                    self.conn.commit()

            cursor.close()

        def get_event_by_id(self, event_id):
            stmt = "SELECT * FROM event WHERE event_id = %s"
            args = (event_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            sql_object = cursor.fetchall()
            name = sql_object[0][1]
            date = sql_object[0][2]
            type = sql_object[0][3]
            total = sql_object[0][5]
            group_id = sql_object[0][4]
            cursor.close()
            return (name, date, type, total, group_id)

        def get_ten_events_by_chat_id(self, chat_id):
            stmt = "SELECT * FROM event WHERE group_id = %s ORDER BY event_id DESC LIMIT 10"
            args = (chat_id,)
            cursor = self.conn.cursor()
            try:
                cursor.execute(stmt, args)
                sql_object = cursor.fetchall()
            except:
                sql_object = [(0, "No Transactions Yet", "", "", "", "")]
            cursor.close()
            return sql_object
            # [(event_id, name, date, type, group_id, total), ]

        def get_txns_by_event_id(self, event_id):
            stmt = "SELECT * FROM txn WHERE event_id = %s"
            args = (event_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            sql_object = cursor.fetchall()
            txn_list = []
            for txn in sql_object:
                txn_list.append((txn[2], txn[3], txn[4]))

            cursor.close()
            # txn_list: [(payor, debtor, amount), (payor, debtor, amount)...]

            return txn_list

        def settle_txn(self, chat_id):
            stmt = "UPDATE txn SET settled_status = 1 WHERE group_id = %s"
            args = (chat_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

        def get_outstanding_txn(self, chat_id):
            stmt = "SELECT * FROM txn WHERE group_id = %s AND settled_status = 0"
            args = (chat_id,)
            cursor = self.conn.cursor()
            try:
                cursor.execute(stmt, args)
                sql_object = cursor.fetchall()
            except:
                sql_object = []

            outstanding_txns = {}
            for tp in sql_object:
                if tp[1] not in outstanding_txns:
                    outstanding_txns[tp[1]] = [(tp[2], tp[3], tp[4])]
                else:
                    outstanding_txns[tp[1]].append((tp[2], tp[3], tp[4]))
            # outstanding_txns: {event_id: [(payor, debtor, amount), (payor, debtor, amount)]...}
            cursor.close()
            return outstanding_txns

        def get_balances(self, chat_id):
            stmt = "SELECT * FROM users WHERE group_id = %s"
            args = (chat_id,)
            cursor = self.conn.cursor()
            user_dict = {}
            cursor.execute(stmt, args)
            sql_array = cursor.fetchall()
            for row in sql_array:
                user_dict[row[0]] = (row[1], row[2])

            # user_dict: {user1_id: ('name', balance), user2_id: ...}
            cursor.close()
            return user_dict

        def add_ps(self, chat_id, sender_id, receiver_id, amount):
            stmt = "INSERT INTO pending_settlements (group_id, sender_id, receiver_id, amount) VALUES (%s,%s,%s,%s)"
            args = (chat_id, sender_id, receiver_id, amount)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

        def get_ps(self, chat_id):
            stmt = "SELECT * FROM pending_settlements WHERE group_id = %s"
            args = (chat_id,)
            cursor = self.conn.cursor()
            ps_dict = {}
            cursor.execute(stmt, args)
            array = cursor.fetchall()
            for row in array:
                if row[2] not in ps_dict:
                    ps_dict[row[2]] = [(row[3], row[4], row[0])]
                else:
                    ps_dict[row[2]].append((row[3], row[4], row[0]))

            # ps_dict: {giver_id: [(receiver1_id, amount, ps_id), (receiver2_id, amount, ps_id)], ..}
            cursor.close()
            return ps_dict

        def delete_ps(self, ps_id):
            stmt = "DELETE FROM pending_settlements WHERE ps_id = %s"
            args = (ps_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

        def clear_ps_by_group(self, chat_id):
            stmt = "DELETE FROM pending_settlements WHERE group_id = %s"
            args = (chat_id,)
            cursor = self.conn.cursor()
            cursor.execute(stmt, args)
            self.conn.commit()
            cursor.close()

def print_tables():
    db = DBHelper()
    db.setup()

    df = pd.read_sql_query("Select * from users", db.conn)
    print(df.head(1000))

    df = pd.read_sql_query("Select * from event", db.conn)
    print(df.head(1000))

    df = pd.read_sql_query("Select * from txn", db.conn)
    print(df.head(1000))

    df = pd.read_sql_query("Select * from pending_settlements", db.conn)
    print(df.head(1000))
