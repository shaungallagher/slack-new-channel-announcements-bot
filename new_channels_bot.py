"""
Each time this script runs (via cron job or similar scheduler), it will check to see whether any
new Slack channels have been added, and if so, it will post a notification message in a designated
Slack channel.  Postgres is used to store the channels, but with minimal tweaking you can use
a different SQL database.

Katsuya Noguchi's https://github.com/kn/slack Python package is used to interact with the Slack API.

"""

import slack
import slack.chat
import slack.channels
import slack.users

import sys

import os
import psycopg2
import urlparse


CONFIG = {
    'api_token': '',   # Learn how to get one: https://api.slack.com/bot-users
    'post_channel': '#announce_new_channels',   # The channel where the bot should announce new channels
    'bot_name': "Hey, There's a New Channel!",   # Displayed each time the bot posts
    'icon_emoji': ":new:",   # The emoji that should be used as the bot's avator in its posts
}


def get_user_by_id(users, user_id):
    return next((user for user in users if user['id'] == user_id), None)


def get_existing_row(cursor, channel_id):
    cursor.execute(
        'SELECT name, created, creator_id, creator_name, topic, purpose FROM channels WHERE channel_id = %s',
        (channel_id,))
    results = cursor.fetchall()
    return results


def get_fields(users, channel):
    name = channel['name']
    created = int(channel['created'])
    creator_id = channel['creator']
    creator_name = get_user_by_id(users, creator_id)['name']
    topic = channel['topic']['value']
    purpose = channel['purpose']['value']
    return name, created, creator_id, creator_name, topic, purpose


def construct_msg(channel_id, name, creator_id, creator_name, purpose, topic):
    msg = [
        u'Channel: <#{}|{}>'.format(channel_id, name),
        u'Creator: <@{}|{}>'.format(creator_id, creator_name),
    ]

    if purpose:
        msg.append(u'Purpose: {}'.format(purpose))
    else:
        purpose = ''
    if topic:
        msg.append(u'Topic: {}'.format(topic))
    else:
        topic = ''

    return "\n".join(msg)


def check_new_channels():

    slack.api_token = CONFIG['api_token']

    channels = slack.channels.list()['channels']
    users = slack.users.list()['members']

    # Connect to Postgres in Heroku.  You may need to connect a
    # different way, depending on your hosting environment.

    urlparse.uses_netloc.append("postgres")
    url = urlparse.urlparse(os.environ["DATABASE_URL"])

    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

    with conn:

        cursor = conn.cursor()

        cursor.execute("CREATE TABLE IF NOT EXISTS channels "
                       "(channel_id VARCHAR(255), name VARCHAR(255), created VARCHAR(31), "
                       "creator_id VARCHAR(63), creator_name VARCHAR(63), topic TEXT, purpose TEXT)")

        for channel in channels:
            channel_id = channel['id']
            results = get_existing_row(cursor, channel_id)
            if len(results) == 0:
                name, created, creator_id, creator_name, topic, purpose = get_fields(users, channel)
                msg_str = construct_msg(channel_id, name, creator_id, creator_name, purpose, topic)

                cursor.execute(
                    "INSERT INTO channels(channel_id, name, created, creator_id, creator_name, topic, purpose) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (channel_id, name, created, creator_id, creator_name, topic, purpose,))

                slack.chat.post_message(
                    CONFIG['post_channel'],
                    msg_str,
                    username=CONFIG['bot_name'],
                    icon_emoji=CONFIG['icon_emoji'])


if __name__ == '__main__':

    sys.exit(check_new_channels())
