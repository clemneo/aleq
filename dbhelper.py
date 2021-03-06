import sqlite3
import pandas as pd


class DBHelper:
    def __init__(self, dbname="prod1.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)

    def setup(self):
        stmt1 = "CREATE TABLE IF NOT EXISTS user (" \
                "user_id integer NOT NULL PRIMARY KEY, " \
                "name TEXT NOT NULL, " \
                "balance integer NOT NULL, " \
                "group_id integer NOT NULL," \
                "UNIQUE(group_id, name)" \
                ")"
        stmt2 = "CREATE TABLE IF NOT EXISTS event (" \
                "event_id integer NOT NULL PRIMARY KEY, " \
                "name TEXT NOT NULL, " \
                "date integer NOT NULL, " \
                "type integer NOT NULL, " \
                "group_id integer NOT NULL," \
                "total integer NOT NULL)"
                # type 0 transaction 1 repayment
        stmt3 = "CREATE TABLE IF NOT EXISTS txn (" \
                "txn_id integer NOT NULL PRIMARY KEY, " \
                "event_id integer NOT NULL," \
                "payer_id integer NOT NULL, " \
                "debtor_id integer NOT NULL, " \
                "amount integer NOT NULL, " \
                "group_id integer NOT NULL, " \
                "settled_status integer NOT NULL," \
                "FOREIGN KEY (payer_id) REFERENCES user (user_id)," \
                "FOREIGN KEY (debtor_id) REFERENCES user (user_id))"
        stmt4 = "CREATE TABLE IF NOT EXISTS pending_settlements (" \
                "ps_id integer NOT NULL PRIMARY KEY," \
                "group_id integer NOT NULL," \
                "sender_id integer NOT NULL," \
                "receiver_id integer NOT NULL," \
                "amount integer NOT NULL," \
                "FOREIGN KEY (sender_id) REFERENCES user (user_id)," \
                "FOREIGN KEY (receiver_id) REFERENCES user (user_id))"
        stmt5 = "CREATE TABLE IF NOT EXISTS timezone_offset (" \
                "group_id integer NOT NULL," \
                "offset_in_seconds integer NOT NULL," \
                "FOREIGN KEY (group_id) REFERENCES user (group_id)" \
                "UNIQUE (group_id))"
        self.conn.execute(stmt1)
        self.conn.execute(stmt2)
        self.conn.execute(stmt3)
        self.conn.execute(stmt4)
        self.conn.execute(stmt5)
        self.conn.commit()

    # def start_bot(self,group_id):
    #     stmt = "INSERT INTO groups (group_id, created_at) VALUES ((?), strftime('%s'))"
    #     args = (group_id, )
    #     self.conn.execute(stmt, args)
    #     self.conn.commit()

    def get_users(self, group_id):
        """tuple list: Returns (x,y,z) where x[n] gives you user_id, y[n] gives you name, z[n] gives you balance"""
        """total list: Returns [(user_id1,username1,balance1),(user_id2,username2,balance2)...]"""
        stmt = "SELECT user_id, name, balance FROM user WHERE group_id = (?)"
        args = (group_id,)
        total_list = [x for x in self.conn.execute(stmt, args)]
        user_id_list = [x[0] for x in total_list]
        name_list = [x[1] for x in total_list]
        balance_list = [x[2] for x in total_list]
        #return (user_id_list, name_list, balance_list)
        return total_list

    def get_id_to_username_dict(self, group_id):
        stmt = "SELECT user_id, name FROM user WHERE group_id = (?)"
        args = (group_id,)
        cursor = self.conn.cursor()
        id_name_dict = {}
        for row in cursor.execute(stmt, args):
            id_name_dict[row[0]] = row[1]

        return id_name_dict

    def add_user(self, name, group_id):
        """Adds a user given a name (string) and group_id (int)"""
        stmt = "INSERT INTO user (name, group_id,balance) VALUES ((?),(?),0)"
        args = (name, group_id,)
        self.conn.execute(stmt, args)
        self.conn.commit()

    def remove_user(self, user_id):
        """Removes a user, but technically just sets the group_id to null"""
        stmt = "UPDATE user SET group_id = NULL WHERE user_id = (?)"
        args = (user_id, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def get_user_id(self, chat_id, name):
        stmt = "SELECT user_id FROM user WHERE group_id = (?) AND name = (?)"
        args = (chat_id, name)
        user_id = [x[0] for x in self.conn.execute(stmt,args)][0]
        return user_id

    def set_timezone_for_group(self, chat_id, offset):
        stmt = "INSERT INTO timezone_offset (group_id, offset_in_seconds) VALUES ((?),(?))"
        args = (chat_id, offset)
        self.conn.execute(stmt,args)
        self.conn.commit()

    def get_timezone(self, chat_id):
        stmt = "SELECT offset_in_seconds FROM timezone_offset WHERE group_id = (?)"
        args = (chat_id,)
        object = [x for x in self.conn.execute(stmt,args)]

        #[(seconds_offset, )]
        return object

    def add_event(self, chat_id, name, date, type, total, payer_id, payees):
        stmt = "INSERT INTO event (name, date, type, group_id, total) VALUES ((?),(?),(?),(?),(?))"
        args = (name, date, type, chat_id, total)

        cursor = self.conn.cursor()
        cursor.execute(stmt, args)
        event_id = cursor.lastrowid
        total_owed = 0

        for debtor_id in payees:
            stmt = "INSERT INTO txn (event_id, payer_id, debtor_id, amount, group_id, settled_status)" + \
                    " VALUES ((?),(?),(?),(?),(?),(?))"
            args = (event_id, payer_id, debtor_id, payees[debtor_id], chat_id, 0)
            self.conn.execute(stmt, args)

            stmt2 = "UPDATE user SET balance = balance + (?) WHERE user_id = (?)"
            args2 = (payees[debtor_id], debtor_id)
            self.conn.execute(stmt2, args2)

            total_owed += payees[debtor_id]

        stmt3 = "UPDATE user SET balance = balance - (?) WHERE user_id = (?)"
        args3 = (total_owed, payer_id)
        self.conn.execute(stmt3, args3)
        self.conn.commit()

        # todo: test repayments settled status update below
        if type == 1:
            stmt4 = "SELECT balance FROM user WHERE group_id = (?)"
            args4 = (chat_id,)
            balances = [x[0] for x in self.conn.execute(stmt4,args4)]
            if all(b == 0 for b in balances):
                stmt5 = "UPDATE txn SET settled_status = 1 WHERE group_id = (?) AND settled_status = 0"
                args5 = (chat_id,)
                self.conn.execute(stmt5, args5)
                self.conn.commit()

    def get_event_by_id(self, event_id):
        stmt = "SELECT * FROM event WHERE event_id = (?)"
        args = (event_id, )
        sql_object = [x for x in self.conn.execute(stmt,args)]
        name = sql_object[0][1]
        date = sql_object[0][2]
        type = sql_object[0][3]
        total = sql_object[0][5]
        group_id = sql_object[0][4]
        return (name, date, type, total, group_id)

    def get_ten_events_by_chat_id(self, chat_id):
        stmt = "SELECT * FROM event WHERE group_id = (?) ORDER BY event_id DESC LIMIT 10"
        args = (chat_id, )
        sql_object = [x for x in self.conn.execute(stmt,args)]
        return sql_object
        # [(event_id, name, date, type, group_id, total), ]

    def get_txns_by_event_id(self, event_id):
        stmt = "SELECT * FROM txn WHERE event_id = (?)"
        args = (event_id, )
        sql_object = [x for x in self.conn.execute(stmt,args)]
        txn_list = []
        for txn in sql_object:
            txn_list.append((txn[2],txn[3],txn[4]))
        # txn_list: [(payor, debtor, amount), (payor, debtor, amount)...]

        return txn_list

    def settle_txn(self, chat_id):
        stmt = "UPDATE txn SET settled_status = 1 WHERE group_id = (?)"
        args = (chat_id,)
        self.conn.execute(stmt, args)
        self.conn.commit()

    def get_outstanding_txn(self, chat_id):
        stmt = "SELECT * FROM txn WHERE group_id = (?) AND settled_status = 0"
        args = (chat_id, )
        sql_object = [x for x in self.conn.execute(stmt, args)]
        outstanding_txns = {}
        for tp in sql_object:
            if tp[1] not in outstanding_txns:
                outstanding_txns[tp[1]] = [(tp[2], tp[3], tp[4])]
            else:
                outstanding_txns[tp[1]].append((tp[2], tp[3], tp[4]))
        # outstanding_txns: {event_id: [(payor, debtor, amount), (payor, debtor, amount)]...}
        return outstanding_txns

    def get_balances(self, chat_id):
        stmt = "SELECT * FROM user WHERE group_id = (?)"
        args = (chat_id,)
        cur = self.conn.cursor()
        user_dict = {}
        for row in cur.execute(stmt, args):
            user_dict[row[0]] = (row[1], row[2])

        # user_dict: {user1_id: ('name', balance), user2_id: ...}
        return user_dict

    def add_ps(self, chat_id, sender_id, receiver_id, amount):
        stmt = "INSERT INTO pending_settlements (group_id, sender_id, receiver_id, amount) VALUES ((?),(?),(?),(?))"
        args = (chat_id, sender_id, receiver_id, amount)
        self.conn.execute(stmt, args)
        self.conn.commit()

    def get_ps(self, chat_id):
        stmt = "SELECT * FROM pending_settlements WHERE group_id = (?)"
        args = (chat_id,)
        cur = self.conn.cursor()
        ps_dict = {}
        for row in cur.execute(stmt, args):
            if row[2] not in ps_dict:
                ps_dict[row[2]] = [(row[3],row[4],row[0])]
            else:
                ps_dict[row[2]].append((row[3],row[4],row[0]))

        # ps_dict: {giver_id: [(receiver1_id, amount, ps_id), (receiver2_id, amount, ps_id)], ..}
        return ps_dict

    def delete_ps(self, ps_id):
        stmt = "DELETE FROM pending_settlements WHERE ps_id = (?)"
        args = (ps_id, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def clear_ps_by_group(self, chat_id):
        stmt = "DELETE FROM pending_settlements WHERE group_id = (?)"
        args = (chat_id, )
        self.conn.execute(stmt, args)
        self.conn.commit()


def print_tables():
    db = DBHelper()
    db.setup()

    df = pd.read_sql_query("Select * from user", db.conn)
    print(df.head(1000))

    df = pd.read_sql_query("Select * from event", db.conn)
    print(df.head(1000))

    df = pd.read_sql_query("Select * from txn", db.conn)
    print(df.head(1000))

    df = pd.read_sql_query("Select * from pending_settlements", db.conn)
    print(df.head(1000))

