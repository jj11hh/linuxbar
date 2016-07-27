#!/usr/bin/env python3


from flask import Flask, Response, request
app = Flask(__name__)

import io
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import forum
import captcha
from validation import *


# Enable debug mode for test
DEBUG = True
EMAIL_ADDRESS = 'no_reply@foo.bar'


def _(string):
    return string # reserved for l10n


def send_mail(subject, addr_from, addr_to, content, html_content=''):
    '''Send an HTML email

    @param str subject
    @param str addr_from
    @param str addr_to
    @param str content
    @return void
    '''
    msg= MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = addr_from
    msg['To'] = addr_to
    msg_plaintext = MIMEText(content)
    if(html_content):
        msg_html = MIMEText(html_content, 'html')
        msg.attach(msg_html)
    msg.attach(msg_plaintext)
    smtp = smtplib.SMTP('localhost')
    smtp.send_message(msg)
    smtp.quit()


def json_response(result):
    '''Generate JSON responses from the return values of functions of forum.py

    @param tuple result (int, str[, dict])
    @return Response
    '''
    formatted_result = {'code': result[0], 'msg': result[1]}
    if(len(result) == 3):
        formatted_result['data'] = result[2]
    return Response(json.dumps(formatted_result), mimetype='application/json')


def validation_err_response(err):
    '''Generate responses for validation errors

    @param ValidationError err
    @return Response
    '''
    return json_response((255, _('Validation error: %s') % str(err)) )


@app.route('/')
def index():
    return '<h1>It just works, but very ugly.</h1>'


@app.route('/captcha/get')
def captcha_get():
    code = captcha.gen_captcha()
    # TODO: session
    image = captcha.gen_image(code)
    output = io.BytesIO()
    image.save(output, format='PNG')
    image_data = output.getvalue()
    return Response(image_data, mimetype='image/png')


@app.route('/api/user/get/name/<int:uid>')
def user_get_name(uid):
    return json_response(forum.user_get_name(uid))


@app.route('/api/user/get/uid/<username>')
def user_get_uid(username):
    try:
        validate_username(_('Username'), username)
    except ValidationError as err:
        return validation_err_response(err)
    return json_response(forum.user_get_uid(username))


@app.route('/api/user/register', methods=['POST'])
def user_register():
    def send_activation_mail(site_name, mail_to, activation_url):
        '''Make an activation mail and send it by `send_mail`

        @param str site_name
        @param str mail_to
        @param str activation_url
        '''
        send_mail(
            subject = 'Activation Mail - %s' % site_name,
            addr_from = EMAIL_ADDRESS,
            addr_to = mail_to,
            content = _('Activation link: ') + activation_url,
            html_content = _('Activation link: ')
                + ('<a target="_blank" href="%s">%s</a>'
                % (activation_url, activation_url))
        )

    mail = request.form['mail']
    name = request.form['name']
    # unencrypted password: TLS is necessary
    password = request.form['password']

    try:
        validate_email(_('Mail address'), mail)
        validate_username(_('Username'))
        validate(_('Password'), password, not_empty=True)
        # TODO: captcha
    except ValidationError as err:
        return validation_err_response(err)

    result = forum.user_register(mail, name, password)
    if(result[0] != 0):
        return json_response(result)
    data = result[2]

    result_config = forum.config_get()
    if(result_config[0] != 0):
        return json_response(result_config)
    config = result_config[2]

    site_name = config['site_name']
    site_url = config['site_url']
    activation_url = (
        '%s/user/activate/%d/%s' % (
            site_url,
            data['uid'],
            data['activation_code']
        )
    )
    # remove info of activation code (very important !!!)
    del data['activation_code']

    try:
        send_activation_mail(site_name, mail, activation_url)
    except Exception as err:
        return json_response((253, _('Failed to send mail: %s') % str(err)) )

    return json_response(result)


# TODO: re-send activation mail


@app.route('/user/activate/<int:uid>/<code>')
def user_activate(uid, code):
    # TODO: change into a page, not API returning unfriendly JSON.
    # And don't forget to change URL sent above.
    try:
        validate_token(_('Activation Code'), code)
    except ValidationError as err:
        return validation_err_response(err)
    return json_response(forum.user_activate(uid, code))


@app.route('/user/password-reset/get-token/<username>')
def user_password_reset_get_token(username):
    try:
        validate_username(_('Username'), username)
    except ValidationError as err:
        return validation_err_response(err)

    result_getuid = form.user_get_uid(username)
    if(result_getuid[0] != 0):
        return json_response(result_getuid)
    uid = result_getuid[2]['uid']

    result = forum.user_password_reset_get_token(uid)
    if(result[0] != 0):
        return json_response(result)
    data = result[2]

    result_config = forum.config_get()
    if(result_config[0] != 0):
        return json_response(result_config)
    config = result_config[2]

    try:
        send_mail(
            subject = _('Password Reset - %s') % config.site_name,
            addr_from = EMAIL_ADDRESS,
            addr_to = data['mail'],
            content = (
                _('Verification Code: %s (Valid in 10 minutes)')
                % data['token']
            )
        )
        del data['token']
        return json_response(result)
    except Exception as err:
        return json_response(253, _('Failed to send mail: %s') % str(err))


@app.route('/user/reset-password/reset', methods=['POST'])
def user_reset_password():
    username = request.form['username']
    token = request.form['token']
    password = request.form['password']

    try:
        validate_username(_('Username'), username)
        validate_token(_('Token'), token)
    except ValidationError as err:
        return validation_err_response(err)

    result_getuid = form.user_get_uid(username)
    if(result_getuid[0] != 0):
        return json_response(result_getuid)
    uid = result_getuid[2]['uid']

    return json_response(forum.user_reset_password(uid, token, password))


if __name__ == '__main__':
    app.run(debug=DEBUG)
