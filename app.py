
from datetime import datetime, timedelta
import json
import gzip
import sqlite3
import requests
import os
import psycopg2
from psycopg2.extras import DictCursor

from datetime import datetime
from bs4 import BeautifulSoup

from apscheduler.schedulers.blocking import BlockingScheduler
from flask import Flask, Response, render_template, g, send_from_directory

app = Flask(__name__, static_url_path='')

# HEROKU
DATABASE_URL = os.environ['DATABASE_URL']
SSL_MODE = 'require'

# LOCAL
# DATABASE_URL = "127.0.0.1"
# SSL_MODE = None


def get_gzipped_response(data):
    response = Response(gzip.compress(bytes(json.dumps(data), 'utf-8')))
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Vary'] = 'Accept-Encoding'
    response.headers['Accept-Charset'] = 'utf-8'
    response.headers['Content-Length'] = len(response.data)
    return response


def send_notification(title: str, body: str):
    x = requests.post("https://fcm.googleapis.com/fcm/send", json={
        "to": "/topics/all",
        "notification": {
            "title": title,
            "body": body
        }
    }, headers={
        'Content-type': 'application/json',
        "Authorization": "key=" + "AAAAh_ImxPE:APA91bFHHx7t3lAxnq4sxIUfxQP6v1FlO7EATk9QD_4hcTIj8BZ1fKL1mp3uXtgeiMrIJ_m2bDNcvP4Xm8BN_Vdt-lk42nCLMD7fhD4yGnQj5LGtC9TYxQoJjGi_gGjJnL2gxOfNeweY"
    })
    return x.content


def get_db() -> sqlite3.Connection:
    db = getattr(g, '_database', None)
    if db is None:
        # LOCAL
        # db = g._database = psycopg2.connect(host=DATABASE_URL, sslmode=SSL_MODE, database='planwat', user='postgres',
        #                                     password='toor')

        # HEROKU
        db = g._database = psycopg2.connect(DATABASE_URL, sslmode='require')
        create_tables(db)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def create_tables(db):
    cur = db.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS homework_update (
        id SERIAL PRIMARY KEY,
        date TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reference (
        id SERIAL PRIMARY KEY,
        name TEXT,
        link TEXT,
        homework TEXT,
        type TEXT,
        homework_update_id INTEGER,
        homework_tags TEXT 
    )""")
    db.commit()


def scrap_page():
    con = get_db()
    cur = con.cursor(cursor_factory=DictCursor)

    cur.execute("select * from homework_update order by id desc limit 1")
    last_update_id = cur.fetchone()
    if last_update_id != None:
        update_id = last_update_id['id'] + 1
    else:
        update_id = 1

    cur.execute("select * from reference")
    myresult = cur.fetchall()
    if not myresult:
        addThisLinks1234()
        cur.execute("select * from reference")
        myresult = cur.fetchall()

    is_updated = False
    for subject in myresult:
        homework = BeautifulSoup(requests.get(subject['link']).text, 'html.parser').find(
            'div', class_="entry-content")
        if homework.text != subject['homework']:
            is_updated = True
            send_notification("Nowa praca domowa",
                              "Przedmiot '" + subject['type'] + "' został zaktualizowany")
            cur.execute('update reference set homework=%s, homework_tags=%s, homework_update_id=%s where id=%s',
                        (homework.text, str(homework), update_id, subject['id']))

    # if is_updated == True:
    cur.execute("insert into homework_update (date) values (%s)", ((datetime.now() + timedelta(hours=2)).strftime("%d.%m.%Y, %H:%M:%S"),))

    con.commit()
    con.close()


def insert_links_once():
    subjects = [
        ('Zbigniew Switek', 'http://zsstaszow.pl/switek-zbigniew/', 'Język polski'),
        ('Krzysztof Janik', 'http://zsstaszow.pl/janik-krzysztof/', 'Język angielski'),
        ('Agnieszka Misterkiewicz',
         'http://zsstaszow.pl/english-class-3-ti/', 'Język angielski'),
        ('Anna Mikus', 'http://zsstaszow.pl/kl-iiiti-jezyk-angielski-zawodowy/',
         'Angielski zawodowy'),
        ('Wojciech Żmuda', 'http://zsstaszow.pl/zmuda-wojciech/', 'Język niemiecki'),
        ('Grażyna Sikora', 'http://zsstaszow.pl/sikora-grazyna/', 'Język Rosyjski'),
        ('Małgorzata Kochanowska',
         'http://zsstaszow.pl/klasa-iii-ti-matematyka/', 'Matematyka'),
        ('Andrzej Fąfara', 'http://zsstaszow.pl/fizyka-3-ti/', 'Fizyka'),
        ('Dorota Kędziora', 'http://zsstaszow.pl/kedziora-dorota/', 'Geografia'),
        ('Janusz Kosowicz', 'http://zsstaszow.pl/kosowicz-janusz/', 'PP'),
        ('Jan Krupa', 'http://zsstaszow.pl/historia-klasa-3ts-3-tom-3-ti/', 'HIS'),
        ('Andrzej Stawiński', 'http://zsstaszow.pl/klasa-3-ti/', 'Projektowanie baz'),
        ('Robert Kochanowski', 'http://zsstaszow.pl/klasa-iii-ti-informa/',
         'Tworzenie aplikacji'),
        ('Tomasz Dygulski', 'http://zsstaszow.pl/tworzenie-aplikacji-i-witryny-internetowe-kl-3ti/',
         'Witryny internetowe'),
        ('Leszek Tarka', 'http://zsstaszow.pl/tarka-leszek/', 'WF gr. 2'),
        ('Krzysztof Drozd', 'http://zsstaszow.pl/wychowanie-fizyczne-iii-ti-1gr/', 'WF gr. 1'),
        ('Karolina Napierała',
         'http://zsstaszow.pl/klasy-iiitb-iiiti-iiitom-wychowanie-fizyczne/', 'WF - ja'),
        ('Sylwester Gaweł', 'http://zsstaszow.pl/gawel-sylwester/', 'Religia')]

    db = get_db()
    for subject in subjects:
        cur = db.cursor()
        cur.execute("""insert into
        reference (name, link, type) 
        values (%s, %s, %s)""", (subject[0], subject[1], subject[2]))
    db.commit()


@app.route('/api/all')
def get_all_teachers():
    cur = get_db().cursor()
    cur.execute("""
select r.id, r.name, r.link, r.homework, r.type, h.date, r.homework_tags
from reference as r, homework_update as h
where r.homework_update_id = h.id
    """)
    return get_gzipped_response(cur.fetchall())


@app.route('/api/<id>')
def get_one_teacher(id: int):
    cur = get_db().cursor()
    cur.execute("SELECT * FROM reference where id=%s", (id,))
    return get_gzipped_response(cur.fetchall())


@app.route('/static/<path:path>')
def send_asset(path):
    return send_from_directory('static', path)


@app.route('/single/<id>')
def single(id: int):
    return render_template('single.html', id=id)


@app.route('/scrap')
def scrap():
    scrap_page()
    return "Ok."


@app.route('/addThisLinks1234')
def addThisLinks1234():
    insert_links_once()
    return "Ok XD"


@app.route('/')
def main():
    cur = get_db().cursor()
    cur.execute("select date from homework_update order by id desc limit 1")
    date = cur.fetchone()
    if date is None:
        date = ['']  # TODO

    return render_template('index.html', last_update=date[0])


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    scheduler.add_job(scrap_page, 'interval', hours=1)
    scheduler.start()
    app.run(debug=True)
