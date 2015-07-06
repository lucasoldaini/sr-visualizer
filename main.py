#!/usr/bin/python

# default modules
import json
from functools import wraps

# installed modules
import flask
import pymongo

# project modules
import config


app = flask.Flask(__name__)
coll = (pymongo.MongoClient()
        .get_database('safety-reports')
        .get_collection('all-orig'))

server_session = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in config.allowed_extensions


def is_valid_login(username, password):
    return username in config.users and password == config.users[username]

def login_required(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        if flask.session.get('username', None) in server_session:
            return method(*args, **kwargs)
        else:
            flask.session.clear()
            return flask.redirect(flask.url_for('login'))
    return wrapper


@app.route('/')
@login_required
def home():
    return flask.render_template('home.html')


@app.route('/logout', methods=['GET'])
@login_required
def logout():
    un = flask.session.pop('username', None)
    server_session.pop(un, None)
    return flask.redirect(flask.url_for('login'))


@app.route('/login', methods=['POST', 'GET'])
def login():
    error = None
    if flask.request.method == 'POST':
        comb = flask.request.form['username'], flask.request.form['password']
        if is_valid_login(*comb):
            un = str(comb[0])
            flask.session['username'] = un
            server_session.setdefault(un, {})
        else:
            error = 'Invalid username/password'
    # the code below is executed if the request method
    # was GET or the credentials were invalid
    if flask.session.get('username', None) is None:
        return flask.render_template('login.html', error=error)
    else:
        return flask.redirect(flask.url_for('home'))


@app.route('/upload', methods=['POST'])
@login_required
def upload():
    un = flask.session['username']
    file_obj = flask.request.files['file']
    if file_obj:
        server_session[un]['all_topics'] = json.load(file_obj)
        return flask.redirect(flask.url_for('navigate'))
    else:
        return flask.redirect(flask.url_for('home'))


@app.route('/navigate', methods=['GET'])
@login_required
def navigate():
    un = flask.session['username']

    # reset current topic
    server_session[un].pop('topic_data', None)
    server_session[un].pop('topic_position', None)

    all_topics = server_session[un].get('all_topics', None)
    if all_topics is not None:
        return flask.render_template('navigate.html',
                                     all_topics=sorted(all_topics.keys()))
    else:
        return flask.redirect(flask.url_for('home'))

@app.route('/report', methods=['GET'])
@app.route('/report/<_id>', methods=['GET'])
@login_required
def report(_id=None):
    un = flask.session['username']

    if _id is None:
        _id = flask.request.args.get('_id', None)

    report = coll.find_one({'_id': _id})
    if report is not None:
        return flask.render_template('report.html', show_nav=False,
                                     record=sorted(report.items()))
    else:
        return flask.render_template('not_found.html')



@app.route('/reset', methods=['GET'])
@login_required
def reset():
    un = flask.session['username']

    server_session[un].pop('all_topics', None)
    server_session[un].pop('topic_data', None)
    server_session[un].pop('topic_position', None)
    return flask.redirect(flask.url_for('home'))


@app.route('/topic', methods=['GET'])
@app.route('/topic/<topic>', methods=['GET'])
@login_required
def topic(topic=None):
    un = flask.session['username']

    if server_session[un].get('all_topics', None) is None:
        flask.redirect(flask.url_for('home'))

    if topic is None:
        topic = server_session[un].get('current_topic', None)
        if topic is None:
            return flask.redirect(url_for('navigate'))
        else:
            return flask.redirect(flask.url_for('topic', topic=topic))
    else:
        server_session[un]['current_topic'] = topic
        server_session[un]['topic_data'] = server_session[un]['all_topics'][topic]

    if server_session[un].get('topic_position', None) is None:
        server_session[un]['topic_position'] = 0

    _id = server_session[un]['topic_data'][server_session[un]['topic_position']]
    record = sorted(coll.find_one({'_id': _id}).iteritems())

    return flask.render_template('report.html', record=record, show_nav=True)


@app.route('/next_report', methods=['POST'])
def next_report():
    un = flask.session['username']

    is_last_pos = (server_session[un]['topic_position'] ==
                   len(server_session[un]['topic_data']) - 1)

    if not is_last_pos:
        server_session[un]['topic_position'] += 1

    return flask.Response({'OK', ''})


@app.route('/prev_report', methods=['POST'])
def prev_report():
    un = flask.session['username']

    is_first_pos = (server_session[un]['topic_position'] == 0)
    if not is_first_pos:
        server_session[un]['topic_position'] -= 1

    return flask.Response({'OK', ''})


if __name__ == '__main__':
    app.debug = config.debug
    app.secret_key = config.secret
    app.run(host=config.host, port=config.port)
