#!/usr/bin/python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, redirect, jsonify, \
    url_for, flash, send_from_directory
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Cuisine, Dish, User
from flask import session as login_session
from datetime import datetime
import random
import string
import logging
from logging.handlers import RotatingFileHandler
import httplib2
import json
from flask import make_response
import requests

# For debugging purpose
# httplib2.debuglevel = 4

app = Flask(__name__)
CLIENT_ID = json.loads(open('client_secrets.json',
                            'r').read())['web']['client_id']
APPLICATION_NAME = 'Cuisine Wise Application'

# Connect to Database and create database session
engine = create_engine('sqlite:///new-cuisinewise.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token
def getLoginState():
    state = ''.join(random.choice(string.ascii_uppercase +
                                  string.digits) for x in xrange(32))
    login_session['state'] = state
    print 'loggedin state - ' + login_session['state']
    return state


@app.route('/gsignin2connect', methods=['POST'])
def gsignin2connect():
    print 'gsignin2connect'
    app.logger.debug('gsignin2connect called')
    state = request.args.get('state')
    idtoken = request.form.get('idtoken')
    print 'data - ' + str(idtoken)
    url = \
        'https://www.googleapis.com/oauth2/v3/tokeninfo?id_token=%s' \
        % idtoken
    h = httplib2.Http()
    data = json.loads(h.request(url, 'GET')[1])

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    login_session['userid'] = data['sub']

    data = {}
    data['userid'] = login_session['email']
    data['username'] = login_session['username']

    json_data = json.dumps(data)
    return json_data


# User Helper Functions
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/gdisconnect', methods=['POST'])
def gdisconnect():
    print 'gdisconnect method'
    loggedin_username = login_session.get('username')
    print 'User name is: ' + str(loggedin_username)

    if loggedin_username is not None:
        del login_session['state']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('''Successfully
                                 disconnected.'''), 200)
        response.headers['Content-Type'] = 'application/json'
        flash("You are now logged out.")
        return response
    else:
        response = make_response(json.dumps('''Current user not
                                                connected.'''), 200)
        response.headers['Content-Type'] = 'application/json'
        return response


# Endpoint1 - Show all cuisines
@app.route('/')
def showCuisines():
    dbcuisines = session.query(Cuisine).order_by(asc(Cuisine.name))
    dbdishes = showlatestDishesWithCuisine()
    username = login_session.get('username')
    print 'username - ' + str(username)
    print 'state - ' + str(login_session.get('state'))
    if login_session.get('state') is None:
        getLoginState()
    return render_template('cuisines.html', cuisines=dbcuisines,
                           latestdishes=dbdishes,
                           STATE=login_session.get('state'),
                           loggedusername=username)


def showlatestDishesWithCuisine():
    dbdishes = session.query(
                Dish.id.label('dish_id'),
                Dish.name.label('dish_name'),
                Cuisine.id.label('cuisine_id'),
                Cuisine.name.label('cuisine_name'),
                Dish.created_on
                ).join(Cuisine).order_by(Dish.created_on.desc()).limit(5).all()

    return dbdishes


# Endpoint2 -  Show dishes specific to Cuisine/Cuisine_id
@app.route('/cuisines/<int:cuisine_id>/dish/')
def showDishes(cuisine_id):
    cuisine = session.query(Cuisine).filter_by(id=cuisine_id).one()
    dishes = session.query(Dish).filter_by(cuisine_id=cuisine_id).all()
    username = login_session.get('username')
    loginid = login_session.get('email')
    return render_template('cuisinedishes.html', items=dishes,
                           cuisine=cuisine, loggedusername=username,
                           loginid=loginid)


# Edit a restaurant
@app.route('/cuisines/<int:cuisine_id>/<int:dish_id>/edit/',
           methods=['GET', 'POST'])
def editDish(dish_id, cuisine_id):
    username = login_session.get('username')
    loginid = login_session.get('email')

    if username is None:
        return showCuisines()
    mydish = session.query(Dish).filter_by(id=dish_id).one()
    if mydish.user_id == loginid:
        if request.method == 'POST':
            cuisine = session.query(Cuisine).filter_by(name=request.form
                                                       ['cuisine']).one()
            timenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            mydish.name = request.form['name']
            mydish.description = request.form['description']
            mydish.cuisine_id = cuisine.id
            mydish.recipe = request.form['recipe']
            mydish.modified_on = timenow
            session.add(mydish)
            session.commit()
            flash('%s Item Successfully Updated' % mydish.name)
            return redirect(url_for('showDishes', cuisine_id=cuisine.id,
                            loggedusername=username))
        else:
            cuisine = session.query(Cuisine).filter_by(id=cuisine_id).one()
            dish = session.query(Dish).filter_by(id=dish_id).one()
            cuisineall = session.query(Cuisine.name).all()
            return render_template('editDishItem.html', dish=dish,
                                   cuisine=cuisine, cuisines=cuisineall,
                                   loggedusername=username)
    else:
        return redirect(url_for('showDishes', cuisine_id=cuisine.id,
                        loggedusername=username))


@app.route('/cuisines/<int:cuisine_id>/<int:dish_id>/editdesc/',
           methods=['GET', 'POST'])
def editDishDesc(dish_id, cuisine_id):
    username = login_session.get('username')
    loginid = login_session.get('email')
    if username is None:
        return showCuisines()
    mydish = session.query(Dish).filter_by(id=dish_id).one()
    if mydish.user_id == loginid:
        if request.method == 'POST':
            cuisine = session.query(Cuisine).filter_by(name=request.form
                                                       ['cuisine']).one()
            timenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            mydish.name = request.form['name']
            mydish.description = request.form['description']
            mydish.cuisine_id = cuisine.id
            mydish.recipe = request.form['recipe']
            mydish.modified_on = timenow
            session.add(mydish)
            session.commit()
            flash('%s Item Successfully Updated' % mydish.name)
            return redirect(url_for('showDescription',
                            cuisine_id=cuisine.id, dish_id=mydish.id,
                            loggedusername=username))
        else:
            cuisine = session.query(Cuisine).filter_by(id=cuisine_id).one()
            dish = session.query(Dish).filter_by(id=dish_id).one()
            cuisineall = session.query(Cuisine.name).all()
            return render_template('editDishItem.html', dish=dish,
                                   cuisine=cuisine, cuisines=cuisineall,
                                   loggedusername=username)

    else:
        return redirect(url_for('showDescription',
                        cuisine_id=cuisine.id, dish_id=mydish.id,
                        loggedusername=username))
# Create a new menu item


@app.route('/restaurant/dish/new/', methods=['GET', 'POST'])
def newDish():
    username = login_session.get('username')
    loginid = login_session.get('email')
    if username is None:
        return showCuisines()
    else:
        if request.method == 'POST':
            cuisine = session.query(Cuisine).filter_by(name=request.form
                                                       ['cuisine']).one()
            timenow = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            newItem = Dish(
                name=request.form['name'],
                picurl='',
                description=request.form['description'],
                cuisine_id=cuisine.id,
                recipe=request.form['recipe'],
                created_on=timenow,
                modified_on=timenow,
                user_id=loginid,
                )
            session.add(newItem)
            session.commit()
            flash('New Menu %s Item Successfully Created' % newItem.name)
            return redirect(url_for('showDishes', cuisine_id=cuisine.id,
                            loggedusername=username))
        else:
            cuisineall = session.query(Cuisine.name).all()
            return render_template('addnewdish.html', cuisines=cuisineall,
                                   loggedusername=username)


# Delete a dish
@app.route('/restaurant/<int:dish_id>/delete', methods=['GET', 'POST'])
def deleteDish(dish_id):
    username = login_session.get('username')
    loginid = login_session.get('email')
    if username is None:
        return showCuisines()
    dish = session.query(Dish).filter_by(id=dish_id).one()
    if dish.user_id == loginid:
        dish = session.query(Dish).filter_by(id=dish_id).one()
        name = dish.name
        if request.method == 'POST':
            session.delete(dish)
            session.commit()
            flash(' %s dish Successfully deleted' % name)
            return redirect(url_for('showDishes',
                            cuisine_id=dish.cuisine_id,
                            loggedusername=username))
        else:
            return render_template('deleteDish.html', dish=dish,
                                   cuisine_id=dish.cuisine_id,
                                   loggedusername=username)

    else:
        return redirect(url_for('showDishes',
                        cuisine_id=dish.cuisine_id,
                        loggedusername=username))


# Show dish description
@app.route('/restaurant/<int:cuisine_id>/dish/<int:dish_id>/',
           methods=['GET', 'POST'])
def showDescription(dish_id, cuisine_id):
    username = login_session.get('username')
    loginid = login_session.get('email')
    cuisine = session.query(Cuisine).filter_by(id=cuisine_id).one()
    dish = session.query(Dish).filter_by(id=dish_id).one()
    return render_template('description.html', dish=dish,
                           cuisine=cuisine, loggedusername=username,
                           loginid=loginid)


@app.route('/cuisines/JSON')
def cuisinesJSON():
    restaurants = session.query(Cuisine).all()
    return jsonify(restaurants=[r.serialize for r in restaurants])


@app.route('/dishes/JSON')
def dishesJSON():
    cuisines = session.query(Dish).all()
    return jsonify(restaurants=[r.serialize for r in cuisines])


@app.route('/latestDishes/JSON')
def showlatestDishesWithCuisineJSON():

    cuisines = session.query(Dish.name).order_by(Dish.created_on.desc())
    for c in cuisines:
        print c

    return jsonify(Cuisines=[r.serialize for r in
                   session.query(Dish).order_by(Dish.created_on.desc())])
    

@app.route('/webhook')
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        if not request.args.get('hub.verify_token') == 'hello':
            return "Verification token mismatch" , 403
        return request.args['hub.challenge'], 200
    return "Hello World", 200


@app.route('/webhook', methods =['POST'])
def webhook():
    data = request.get_json()
    print data




if __name__ == '__main__':
    handler = RotatingFileHandler('cuisinewise.log',
                                  maxBytes=10000, backupCount=1)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('''%(asctime)s - %(name)s -
                                    %(levelname)s - %(message)s''')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.info('Application started')

    app.secret_key = 'my_super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
