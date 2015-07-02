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


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in config.allowed_extensions


def is_valid_login(username, password):
    return username in config.users and password == config.users[username]


def login_required(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        if 'username' in flask.session:
            return method(*args, **kwargs)
        else:
            return flask.redirect(flask.url_for('login'))
    return wrapper


@app.route('/')
@login_required
def home():
    return flask.render_template('home.html')


@app.route('/logout', methods=['GET'])
@login_required
def logout():
    flask.session.pop('username', None)
    return flask.redirect(flask.url_for('login'))


@app.route('/login', methods=['POST', 'GET'])
def login():
    error = None
    if flask.request.method == 'POST':
        comb = flask.request.form['username'], flask.request.form['password']
        if is_valid_login(*comb):
            flask.session['username'] = comb[0]
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
    file_obj = flask.request.files['file']
    if file_obj:
        flask.session['all_topics'] = json.load(file_obj)
        return flask.redirect(flask.url_for('navigate'))
    else:
        return flask.redirect(flask.url_for('home'))


@app.route('/navigate', methods=['GET'])
@login_required
def navigate():

    # reset current topic
    flask.session.pop('topic_data', None)
    flask.session.pop('topic_position', None)

    all_topics = flask.session.get('all_topics', None)
    if all_topics is not None:
        return flask.render_template('navigate.html',
                                     all_topics=sorted(all_topics.keys()))
    else:
        return flask.redirect(flask.url_for('home'))

@app.route('/report', methods=['GET'])
@app.route('/report/<_id>', methods=['GET'])
@login_required
def report(_id=None):

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
    flask.session.pop('all_topics', None)
    flask.session.pop('topic_data', None)
    flask.session.pop('topic_position', None)
    return flask.redirect(flask.url_for('home'))


@app.route('/topic', methods=['GET'])
@app.route('/topic/<topic>', methods=['GET'])
@login_required
def topic(topic=None):

    if flask.session.get('all_topics', None) is None:
        flask.redirect(flask.url_for('home'))

    if topic is None:
        topic = flask.session.get('current_topic', None)
        if topic is None:
            return flask.redirect(url_for('navigate'))
        else:
            return flask.redirect(flask.url_for('topic', topic=topic))
    else:
        flask.session['current_topic'] = topic
        flask.session['topic_data'] = flask.session['all_topics'][topic]

    if flask.session.get('topic_position', None) is None:
        flask.session['topic_position'] = 0

    _id = flask.session['topic_data'][flask.session['topic_position']]
    record = sorted(coll.find_one({'_id': _id}).iteritems())

    return flask.render_template('report.html', record=record, show_nav=True)


@app.route('/next_report', methods=['POST'])
def next_report():
    is_last_pos = (flask.session['topic_position'] ==
                   len(flask.session['topic_data']) - 1)

    if not is_last_pos:
        flask.session['topic_position'] += 1

    return flask.Response({'OK', ''})


@app.route('/prev_report', methods=['POST'])
def prev_report():

    is_first_pos = (flask.session['topic_position'] == 0)
    if not is_first_pos:
        flask.session['topic_position'] -= 1

    return flask.Response({'OK', ''})


if __name__ == '__main__':
    app.debug = config.debug
    app.secret_key = config.secret
    app.run(host=config.host, port=config.port)
