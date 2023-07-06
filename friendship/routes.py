import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash,  redirect, request, abort, session, jsonify, Response
from friendship.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, SendRequestForm, GoogleRegistrationForm
from friendship.models import User, Post, HelpRequest, Review, Notification
from friendship import app, db, bcrypt,neo4j_driver
from flask_login import login_user, current_user, logout_user, login_required
import pycountry
from authlib.integrations.flask_client import OAuth
import random
import string
import json
from datetime import datetime, date
from sqlalchemy import func, desc
#pip install request




# Context processor to inject notifications into the template context
# This function retrieves the user's notifications and unread count, sorts and limits the notifications,
# and injects them into the template context for display.
@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        if current_user.notifications:
            notifications = current_user.notifications
            notifications=sorted(notifications, key=lambda p: p.date_created, reverse=True)
            notifications=notifications[:6]
            return dict(notifications=notifications, unread_count=current_user.unread_notifications_counter)
        else:
            return dict(notifications=[], unread_count=0)
    else:
        return dict()




# Template filter to convert a string representation of a dictionary into a dictionary object
@app.template_filter('string_to_dict')
def string_to_dict(value):
    return json.loads(value)





""" 
Sends a notification to a user by adding it to the database, updating the unread notification count,
and committing the changes to the database.
Args:
    notification: The notification to send.
"""
def send_notification(notification):
    #add notification to DB
    db.session.add(notification)
    db.session.commit()

    #increment unread_notification_counter of the user who received the notification
    notification.user.unread_notifications_counter+=1
    db.session.commit()




"""
    Recommends popular delivery users to a given user based on various factors.
    Connects to a Neo4j graph database, retrieves user information, and performs a query to find relevant delivery users,
    Scores the delivery users based on rating, review count, and city match,
    Returns a list of recommended delivery users sorted in descending order of their scores 
"""
def recommend_popular_delivers(user_id):
    # Connect to Neo4j database
    session = neo4j_driver.session()

    # Retrieve user's information
    user_query = """
       MATCH (u:User)
       WHERE u.id = $user_id
       RETURN u.city AS city, u.country AS country
       """
    user_result = session.run(user_query, user_id=user_id).single()
    user_city = user_result["city"]


    delivers_query = """
        MATCH (u:User {id: $user_id})
        WITH u.country AS userCountry
        MATCH (users:User)
        WHERE users.country = userCountry AND users.rating_as_deliver>=4 AND  users.id <> $user_id
                AND users.reviews_deliver_counter>=20
        RETURN users.id AS deliver_id, users.city AS deliver_city, users.rating_as_deliver AS deliver_rating,
                    users.reviews_deliver_counter AS deliveries_counter
        """
    delivers_results = session.run(delivers_query, user_id=user_id)
    delivers_scores = []
    max_deliveries_num=100 #suppuse 100 is the highest number of deliveries that a user ever done
    for deliver in delivers_results:
        deliver_id = deliver["deliver_id"]
        print(deliver_id)
        deliver_city = deliver["deliver_city"]
        deliver_rating = deliver["deliver_rating"]
        reviews_deliver_counter = deliver["deliveries_counter"]


        normalized_rating = (deliver_rating - 0) / (5 - 0)
        normalized_review_counter = reviews_deliver_counter / max_deliveries_num
        if deliver_city==user_city:
            city_score=1
        else:
            city_score=0

        score=0.5*normalized_rating +0.2*normalized_review_counter +0.3*city_score

        delivers_scores.append((deliver_id, score))


    delivers_scores.sort(key=lambda x: x[1], reverse=True)
    #print(delivers_scores)
    recommended_delivers = [deliver_id for deliver_id, _ in delivers_scores]


    return recommended_delivers




#This function retrieves a list of popular delivers for the current user based on recommendations.
def get_popular_delivers(user):
    if user==current_user:
        delivers=recommend_popular_delivers(user.id)
        if delivers:
            users_delivers_suggestions = db.session.query(User).filter(User.id.in_(delivers)).all()
            users_delivers_suggestions.sort(key=lambda user: delivers.index(user.id))
            return users_delivers_suggestions
    else:
        return None


# This function updates the rating attributes for a delivery user
# in both the relational database and the Neo4j graph database
def update_deliver_rating_attributes(user_id, rating):
    user=db.session.query(User).get_or_404(user_id) # Retrieve the user from the relational database

    # Update the sum of ratings and the number of reviews in the relational database
    sum=user.sum_rates_as_deliver+rating
    num=user.num_rates_as_deliver+1

    user.sum_rates_as_deliver=sum
    user.num_rates_as_deliver=num
    db.session.commit()

    # Calculate the average rating
    average_rating = sum / num
    average_rating = round(average_rating, 1)

    # Update the rating and reviews counter in the Neo4j graph database
    with neo4j_driver.session() as session:
        result = session.run(
            "MATCH (u:User {id: $user_id}) "
            "SET u.rating_as_deliver = $average_rating,"
            "u.reviews_deliver_counter= $num "
            "RETURN u",
            user_id=user_id,
            average_rating=average_rating,
            num=num
        )



# This route handles the home page of the application.
# It retrieves and filters posts based on the user's preferences.
@app.route("/")
def home():
    if current_user.is_authenticated:
        countries=[country.name for country in pycountry.countries]  # Retrieve a list of countries using the pycountry library

        # Retrieve selected countries, price ranges, minimum tip amount, and sort order from request query parameters
        selected_countries = request.args.getlist('countries')
        price_ranges=['$0 - $20','$20 - $50','$50 - $100','$100 - $200','$200 - $500','$500+']
        selected_price_ranges = request.args.getlist('price_ranges')
        selected_min_tip_amount = request.args.get('min_tip_amount')
        selected_sort_by = request.args.get('sort_by', 'latest')  # default sorting is latest

        friend_ids = current_user.get_friends()  # Retrieve friend IDs of the current user
        if friend_ids:

            if not selected_countries and not selected_price_ranges:
                posts = Post.query.filter(Post.user_id.in_(friend_ids),Post.accepted_help_request_id.is_(None)).all()  # all posts in DB

            elif not selected_countries: # Fetch posts filtered by selected price ranges for the user's friends
                posts = Post.query.filter(Post.user_id.in_(friend_ids),Post.accepted_help_request_id.is_(None),Post.price_range.in_(selected_price_ranges)).all()

            elif not selected_price_ranges: # Fetch posts filtered by selected countries for the user's friends
                posts = Post.query.filter(Post.user_id.in_(friend_ids),Post.accepted_help_request_id.is_(None),Post.country.in_(selected_countries)).all()

            else: # Fetch posts filtered by selected countries and price ranges for the user's friends
                posts = Post.query.filter(Post.user_id.in_(friend_ids),Post.accepted_help_request_id.is_(None),Post.country.in_(selected_countries), Post.price_range.in_(selected_price_ranges)).all()

            if selected_min_tip_amount == 'Any'or selected_min_tip_amount is None:
                pass  # Do nothing, all posts will be included

            else: # Filter posts by minimum tip amount
                #print(selected_min_tip_amount)
                posts = [post for post in posts if post.tip_amount >= float(selected_min_tip_amount)]

            if selected_sort_by == 'latest': # Sort posts by latest date posted
                posts = sorted(posts, key=lambda p: p.date_posted, reverse=True)
            elif selected_sort_by == 'oldest': # Sort posts by oldest date posted
                posts = sorted(posts, key=lambda p: p.date_posted)

        else: # No friends, so no posts to display
            posts=[]
        return render_template('home.html', posts=posts,countries=countries, price_ranges=price_ranges,
                        selected_countries=selected_countries, selected_price_ranges=selected_price_ranges,
                               selected_min_tip_amount=selected_min_tip_amount, selected_sort_by=selected_sort_by)
    else:
        return redirect(url_for('login'))



# This route handles the "about" page of the application.
# It renders the about.html template with the title set to "About".
@app.route("/about")
def about():
    return render_template('about.html', title='About')






""" This route handles the registration page of the application.
It allows users to create a new account by filling out the registration form.
Upon successful registration, the user's account details are saved in the database,
and a corresponding node is created in the Neo4j graph database. 
If the user is already authenticated, they are redirected to the home page."""

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=RegistrationForm()

    if request.method == 'POST':  # Check if the request method is POST
        country_code = form.country.data
        country_name = pycountry.countries.get(alpha_2=country_code).name

        # Update the choices of the city field based on the selected country
        form.populate_city_choices(form.country.data)


    if form.validate_on_submit(): #if our form validated when it was submitted
        #save hashed pwd into db
        hashed_password=bcrypt.generate_password_hash(form.password.data).decode('utf-8') #decode for a string instead of bytes

        country_code = form.country.data
        country_name = pycountry.countries.get(alpha_2=country_code).name
        user = User(username=form.username.data,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    email=form.email.data,
                    password=hashed_password,
                    country=country_name,
                    city=form.city.data,
                    phone_code=form.phone_code.data,
                    phone_number=form.phone_number.data)


        db.session.add(user)
        db.session.commit()

        # Create a corresponding node in Neo4j
        user.create_node_in_neo4j()

        flash('Your account has been created ! You are now able to log in', 'success')#flash message - way to send a one time alert,
                                                                                        # sucssess is a bootstrap category
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)





#This route handles the login functionality of the application.
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form=LoginForm()
    if form.validate_on_submit(): #if our form validated when it was submitted
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data): #if user exist and the password that was entered is valid
            login_user(user, remember=form.remember.data)
            next_page= request.args.get('next') #args is a dictionary. if next key does not exist, it returns none
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Please check email and password', 'danger') #danger- red alert
    return render_template('login.html', title='Login', form=form)



#This route handles the logout functionality of the application.
@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))



#save user's uploaded image to our file system
def save_picture(form_picture,size,path):
    random_hex = secrets.token_hex(8)
    #save file with the same extension as it was uploaded
    _, f_ext = os.path.splitext(form_picture.filename) #the function return 2 values:
                                                       # 1.filename without the extension 2.the extension itself

    picture_filename=random_hex + f_ext #a random filename with the same extension
    picture_path = os.path.join(app.root_path,path, picture_filename)
    output_size=(size,size )#resize the picture before save
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path) #we save the  resized picture in the file system
    return picture_filename





"""This route handles the account editing functionality.
Users can edit their personal details, including name, username,
 email, location, phone number, and profile picture. 
 The changes are saved to the database, and the user's node
  in the Neo4j graph database is updated accordingly"""

@app.route("/edit-account", methods=['GET', 'POST'])
@login_required
def account(): #edit your account
    form = UpdateAccountForm()
    if request.method == 'POST':  # Check if the request method is POST
        country_code = form.country.data
        country_name = pycountry.countries.get(alpha_2=country_code).name

        # Update the choices of the city field based on the selected country
        form.populate_city_choices(form.country.data)

    if form.validate_on_submit(): #if our form validated when it was submitted
        if form.picture.data:
            picture_filename=save_picture(form.picture.data, 125, 'static/profile_pics') #save the picture in the file system
            current_user.image_file = picture_filename #save the picture's filepath in db
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.username = form.username.data
        current_user.email = form.email.data

        country_code = form.country.data
        country_name = pycountry.countries.get(alpha_2=country_code).name
        current_user.country=country_name

        current_user.city=form.city.data
        current_user.phone_code=form.phone_code.data
        current_user.phone_number=form.phone_number.data
        db.session.commit() #update user's details on local database

        #update user's node on neo4j
        with neo4j_driver.session() as session:
            result = session.run(
                "MATCH (u:User {id: $user_id}) "
                "SET u.username = $username,"
                "u.city= $city,"
                "u.country = $country "
                "RETURN u",
                user_id=current_user.id,
                username=form.username.data,
                city=form.city.data,
                country=country_name,

            )
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account')) #post get redirect pattern

    elif request.method=='GET': #fiil forms with current user's info, when user get in the account page
        form.first_name.data=current_user.first_name
        form.last_name.data=current_user.last_name
        form.username.data=current_user.username
        form.email.data=current_user.email
        country_code = pycountry.countries.get(name=current_user.country).alpha_2
        form.country.data = country_code
        form.populate_city_choices(form.country.data)
        form.city.data=current_user.city
        form.phone_code.data=current_user.phone_code
        form.phone_number.data=current_user.phone_number
    image_file= url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account', image_file=image_file, form=form)




#This function categorizes a given price into different price range intervals
def get_price_range(price):
    if price <=20:
        return '$0 - $20'
    elif 20<price<=50:
        return '$20 - $50'
    elif 50<price<=100:
        return '$50 - $100';
    elif 100<price<=200:
        return '$100 - $200'
    elif 200<price<=500:
        return '$200 - $500'
    elif 500<price:
        return '$500+'






"""This route handles the creation of a new product request (post).
 Users can submit a form with information about their request, including the product details and pricing. 
 The post is then saved to the database, and an optional picture can be uploaded. 
 After successful creation, the user is redirected to the home page"""

@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form= PostForm()
    if form.validate_on_submit():
        if not form.price.data and not form.price_range.data:
            flash('Please enter a specific price or choose a price range.', 'danger')
            return render_template('create_post.html', title='New Request', form=form, legend='New Request')
        #save post in db
        if form.picture.data:
            picture_filename = save_picture(form.picture.data, 250, 'static/post_pics')
            if form.price.data:
                range=get_price_range(form.price.data)
                post=Post(product_name=form.product_name.data, country=form.country.data, price_range=range,
                        tip_amount=form.tip_amount.data,content=form.content.data, author=current_user,
                          image_file=picture_filename, price=form.price.data)
                db.session.add(post)
                db.session.commit()
            else:
                post=Post(product_name=form.product_name.data, country=form.country.data, price_range=form.price_range.data,
                        tip_amount=form.tip_amount.data,content=form.content.data, author=current_user, image_file=picture_filename)
                db.session.add(post)
                db.session.commit()

        else:
            if form.price.data:
                range = get_price_range(form.price.data)
                post=Post(product_name=form.product_name.data, country=form.country.data, price_range=range,
                        tip_amount=form.tip_amount.data,content=form.content.data, author=current_user, price=form.price.data)
                db.session.add(post)
                db.session.commit()
            else:
                post=Post(product_name=form.product_name.data, country=form.country.data, price_range=form.price_range.data,
                        tip_amount=form.tip_amount.data,content=form.content.data, author=current_user)
                db.session.add(post)
                db.session.commit()
        flash('Your request has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Request', form=form, legend='New Request')



"""This route displays a specific post based on the provided post ID. 
If the post does not exist, a 404 error is returned"""
@app.route("/post/<int:post_id>")
@login_required
def post(post_id):
    post=db.session.query(Post).get_or_404(post_id) #if post does not exist, then return 404
    return render_template('post.html', title=post.product_name, post=post)



#This route allows logged-in users to update their own posts.
@app.route("/post/<int:post_id>/update",  methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post=db.session.query(Post).get_or_404(post_id) #if post does not exist, then return 404
    if post.author != current_user: #verify that the post belongs to the current user
        abort(403)
    if post.help_requests:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_filename = save_picture(form.picture.data, 250, 'static/post_pics')
            post.image_file=picture_filename

        if form.price.data:
            post.price=form.price.data
            post.price_range=get_price_range(form.price.data)
        else: #no price
            post.price_range = form.price_range.data

        post.product_name= form.product_name.data
        post.country = form.country.data
        post.tip_amount=form.tip_amount.data
        post.content = form.content.data
        db.session.commit() #update db
        flash('Your request has been updated!','success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':  #filling the form with current post data
        form.product_name.data=post.product_name
        form.country.data = post.country

        if post.price:
            form.price.data=post.price

        form.price_range.data = post.price_range
        form.tip_amount.data= post.tip_amount
        form.content.data=post.content
    return render_template('create_post.html', title='Edit Request', form=form, legend='Edit Request')




#This function calculates the average rating and total
# number of reviews for a given list of reviews.
# It returns the average rating and number of reviews
def calc_review_avg(reviews):
    sum_rating=0
    num_reviews = 0
    average_rating = 0;
    if reviews:
        for review in reviews:
            num_reviews += 1
            sum_rating += review.rating
        average_rating = sum_rating / num_reviews
        average_rating = round(average_rating, 1)
    return average_rating,num_reviews




#This function retrieves friend suggestions for a given user,
#using the get_friends_suggestions() method.
def get_suggestions(user):
    if(user==current_user):
        suggestions=user.get_friends_suggestions()
        if suggestions:
            users_suggestions = db.session.query(User).filter(User.id.in_(suggestions)).all()
            users_suggestions.sort(key=lambda user: suggestions.index(user.id))
            return users_suggestions
    else:
        return None




#This function retrieves the friends of a given user.
# If the user has friends, it returns the user objects and their count.
# If the user has no friends, it returns None and a count of 0.
def get_friends(user):
    friends=user.get_friends()
    if friends:
        user_friends=db.session.query(User).filter(User.id.in_(friends)).all()
        return user_friends, len(user_friends)
    else:
        return None,0




"""This route function displays the account/profile page of a user, 
including their basic information.It also handles filtering options for posts (product requests)."""
@app.route("/<string:username>")
@login_required
def view_account(username):
    user=User.query.filter_by(username=username).first_or_404() # Query the user from the database
    image_file = url_for('static', filename='profile_pics/' + user.image_file)
    selected_filter_by = request.args.get('filter_by', 'All')  #Get the selected filter option from the request arguments
    num_reviews=0
    average_rating=0
    if user.reviews_received:
        # Calculate average rating and number of reviews received by the user
        average_rating, num_reviews=calc_review_avg(user.reviews_received)

    suggestions=get_suggestions(user) #people that the user may know
    friends,num_friends=get_friends(user) #user's friends and number of friends
    delivers_suggestions=get_popular_delivers(user) #recommended delivers for the user


    posts=None
    if user.posts: # Retrieve posts based on the selected filter option
        if selected_filter_by == 'All':
            posts=Post.query.filter_by(user_id=user.id, is_arrived_confirmed=False).order_by(desc(Post.date_posted)).all()
        elif selected_filter_by == 'Open for delivery offers':
            posts=Post.query.filter_by(user_id=user.id, accepted_help_request_id=None).order_by(desc(Post.date_posted)).all()
        elif selected_filter_by == 'Delivery in process':
            posts = Post.query.filter(Post.user_id == user.id, Post.accepted_help_request_id.isnot(None),
                                      Post.is_arrived_confirmed.is_(False)).order_by(desc(Post.date_posted)).all()
    return render_template('view_account.html', title=user.username, user=user, image_file=image_file,
                           average_rating=average_rating, num_reviews=num_reviews, posts=posts,
                           selected_filter_by=selected_filter_by, suggestions=suggestions, friends=friends, num_friends=num_friends,
                           delivers_suggestions=delivers_suggestions)





"""This route function displays the reviews on account/profile page of a user. 
It also handles filtering options for the reviews."""

@app.route("/reviews/<string:username>")
@login_required
def view_account_reviews(username):
    user = User.query.filter_by(username=username).first_or_404()
    image_file = url_for('static', filename='profile_pics/' + user.image_file)
    selected_filter_by = request.args.get('filter_by', 'All')
    num_reviews = 0
    average_rating = 0;
    deliver_avg=0;
    recipient_avg=0
    reviews=None

    suggestions = get_suggestions(user)
    friends,num_friends=get_friends(user)
    delivers_suggestions=get_popular_delivers(user)

    if user.reviews_received:
        reviews=user.reviews_received
        average_rating, num_reviews=calc_review_avg(reviews)


        if selected_filter_by == 'All': # Retrieve reviews based on the selected filter option
            reviews = Review.query.filter_by(reviewed_id=user.id).order_by(desc(Review.date_added)).all()
        elif selected_filter_by == 'Rated As A Deliver':
            reviews = Review.query.filter_by(reviewed_id=user.id, is_deliver=True).order_by(desc(Review.date_added)).all()
            deliver_avg,num=calc_review_avg(reviews)
        elif selected_filter_by == 'Rated As A Recipient':
            reviews = Review.query.filter_by(reviewed_id=user.id, is_recipient=True).order_by(desc(Review.date_added)).all()
            recipient_avg,num=calc_review_avg(reviews)
    return render_template('view_account_reviews.html', title=user.username, user=user, image_file=image_file,
                           average_rating=average_rating, num_reviews=num_reviews, reviews=reviews,
                           selected_filter_by=selected_filter_by, deliver_avg=deliver_avg, recipient_avg=recipient_avg,
                           suggestions=suggestions, friends=friends, num_friends=num_friends,
                           delivers_suggestions=delivers_suggestions)






#This route function displays the completed product requests of user on account/profile page of a user.
@app.route("/completed_product_requests/<string:username>")
@login_required
def completed_product_requests(username):
    user=User.query.filter_by(username=username).first_or_404()
    image_file = url_for('static', filename='profile_pics/' + user.image_file)
    num_reviews=0
    average_rating=0
    if user.reviews_received:
        average_rating, num_reviews=calc_review_avg(user.reviews_received)
    suggestions = get_suggestions(user)
    friends,num_friends=get_friends(user)
    delivers_suggestions=get_popular_delivers(user)

    # Retrieve completed product requests from the database
    posts = Post.query.filter_by(user_id=user.id, is_arrived_confirmed=True).order_by(desc(Post.date_posted)).all()
    return render_template('view_account_completed_posts.html', title=user.username, user=user, image_file=image_file,
                           average_rating=average_rating, num_reviews=num_reviews, posts=posts, suggestions=suggestions,
                           friends=friends, num_friends=num_friends, delivers_suggestions=delivers_suggestions)




"""This route function displays the delievry offers of a user on their account/profile page. 
It also handles filtering options for the offers."""

@app.route("/delivery_offers/<string:username>")
@login_required
def view_account_delivery_offers(username):
    user=User.query.filter_by(username=username).first_or_404()
    image_file = url_for('static', filename='profile_pics/' + user.image_file)
    selected_filter_by = request.args.get('filter_by', 'All')  # default sorting is latest
    num_reviews=0
    average_rating=0
    if user.reviews_received:
        average_rating, num_reviews=calc_review_avg(user.reviews_received)
    suggestions=get_suggestions(user)
    friends,num_friends=get_friends(user)
    delivers_suggestions=get_popular_delivers(user)

    # Retrieve help requests (delivery offers) sent by the user from the database
    helpRequests =user.help_requests_sent
    if helpRequests: # Filter the help requests based on the selected filter option
        if selected_filter_by == 'All':
            helpRequests=HelpRequest.query.filter_by(sender_id=user.id, is_cancelled=False, is_completed=False).order_by(desc(HelpRequest.date_sent)).all()
        elif selected_filter_by == 'Accepted':
            helpRequests=HelpRequest.query.filter_by(sender_id=user.id, is_cancelled=False, accepted=True, is_completed=False).order_by(desc(HelpRequest.date_sent)).all()
        elif selected_filter_by == 'Pending':
            helpRequests=HelpRequest.query.filter_by(sender_id=user.id, is_cancelled=False, accepted=False).order_by(desc(HelpRequest.date_sent)).all()


    return render_template('view_account_delivery_offers.html', title=user.username, user=user, image_file=image_file,
                           average_rating=average_rating, num_reviews=num_reviews, helpRequests=helpRequests,
                           suggestions=suggestions, friends=friends, num_friends=num_friends,
                           delivers_suggestions=delivers_suggestions,selected_filter_by=selected_filter_by)




#This route function displays the completed delievry offers of a user on their account/profile page.
@app.route("/completed_deliveries/<string:username>")
@login_required
def completed_deliveries(username):
    user=User.query.filter_by(username=username).first_or_404()
    image_file = url_for('static', filename='profile_pics/' + user.image_file)
    num_reviews=0
    average_rating=0
    if user.reviews_received:
        average_rating, num_reviews=calc_review_avg(user.reviews_received)
    suggestions = get_suggestions(user)
    friends,num_friends=get_friends(user)
    delivers_suggestions=get_popular_delivers(user)


    # Retrieve completed and cancelled help requests of the user from the database
    completed_requests  = HelpRequest.query.filter_by(sender_id=user.id, is_completed=True).order_by(
        desc(HelpRequest.date_sent)).all()
    cancelled_requests  = HelpRequest.query.filter_by(sender_id=user.id, is_cancelled=True).order_by(
        desc(HelpRequest.date_sent)).all()

    # Combine completed and cancelled requests and sort them by date sent in descending order
    helpRequests=completed_requests+cancelled_requests
    helpRequests.sort(key=lambda x: x.date_sent, reverse=True)
    return render_template('view_account_completed_deliveries.html', title=user.username, user=user, image_file=image_file,
                           average_rating=average_rating, num_reviews=num_reviews, helpRequests=helpRequests, suggestions=suggestions,
                           friends=friends, num_friends=num_friends, delivers_suggestions=delivers_suggestions)




#This route handles the display of a user's friends.
@app.route("/friends/<string:username>")
@login_required
def friends(username):
    user = User.query.filter_by(username=username).first_or_404() # Query the user from the database
    friends, num_friends = get_friends(user) # Get the user's friends and the number of friends
    return render_template('friends.html', title=user.username+" friends", user=user, friends=friends, num_friends=num_friends)




###old function ####
@app.route("/help_requests_history")
@login_required
def view_help_requests_history():
    return render_template('help_requests_history.html', title='help_requests_history')



#This route handles the display of all notifications for a specific user.
@app.route("/notifications/<int:user_id>")
@login_required
def notifications(user_id):
    if current_user.id!=user_id:
        abort(403)
    notifications=[] # Initialize an empty list to store notifications
    if current_user.notifications: # Check if the current user has any notifications
        notifications = current_user.notifications # Get the notifications for the current user
        notifications = sorted(notifications, key=lambda p: p.date_created, reverse=True) # Sort notifications by date in descending order
    return render_template('notifications.html', title="notifications", notifications=notifications)




#This route handles the deletion of a specific post (product request).
@app.route("/post/<int:post_id>/delete",  methods=['POST'])
@login_required
def delete_post(post_id):
    post=db.session.query(Post).get_or_404(post_id) # Retrieve the post with the given post_id from the database. if post does not exist, then return 404
    if post.author != current_user: # Check if the current user is the author of the post
        abort(403) # If not, abort with a 403 Forbidden error


    if post.accepted_help_request: # Check if the post has an accepted help request (delivery in process/arrived/confirmed)
        abort(403) # If yes, abort with a 403 Forbidden error

    #delete help requests before delete the post
    help_requests = HelpRequest.query.filter_by(post_id=post.id).all()
    for help_request in help_requests:
        db.session.delete(help_request)


    db.session.delete(post) # Delete the post from the database
    db.session.commit() # Commit the changes
    flash('Your request has been deleted!', 'success') # Display a success flash message
    return redirect(url_for('home')) # Redirect the user to the home page





#This function handles the sending of a delivery offer (help request) for a post, including validations and notifications
@app.route("/send_help_request/<int:post_id>", methods=["POST"])
@login_required
def send_help_request(post_id):
    post = Post.query.get_or_404(post_id) # Retrieve the post with the given post_id from the database

    if post.author == current_user:
        return jsonify(message="Invalid request"), 400 # Return an error response if the user is the author

    if post.accepted_help_request:
        return jsonify(message="Invalid request"), 400 # Return an error response if there is an accepted help request

    help_request = HelpRequest.query.filter_by(post_id=post.id, sender_id=current_user.id).first()

    if help_request: # Check if the current user has already sent a help request
        return jsonify(message="Help request already sent"), 400 # Return an error response

    tip_amount = request.json.get("tip_amount") # Retrieve the delivery fee from the request JSON data
    try:
        tip_amount = float(tip_amount) # Convert it to a float
        if tip_amount <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify(message="Invalid tip amount"), 400

    date = request.json.get("date") # Retrieve the delivery date from the request JSON data
    # Check if the date is in the correct format and not in the past
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        if date_obj < datetime.utcnow().date():
            return jsonify(message='Invalid date. Please choose a future date.'), 400
    except ValueError:
        return jsonify(message='Invalid date format. Please use YYYY-MM-DD.'), 400

    # Create a new help request
    help_request = HelpRequest(post_id=post.id, sender_id=current_user.id, tip_amount=tip_amount, last_delivery_date=date_obj)
    db.session.add(help_request) # Add the help request to the database
    db.session.commit() # Commit the changes

    # Create a notification for the post author about the new delivery offer
    notification = Notification(content=current_user.first_name + " "+current_user.last_name +" sent you a delivery offer",
                                endpoint='post', args = '{"post_id": ' + str(post.id) + '}',
                                user_id=post.author.id, sender_id=current_user.id)
    send_notification(notification) # Send the notification


    return jsonify(message="Help request sent"), 200 # Return a success response





#This function handles the change of tip amount (delivery fee) for a help request (delivery offer) associated with a post.
#It includes validations and notifications for both the sender and the post author.
@app.route("/change_tip_amount/<int:request_id>", methods=["POST"])
@login_required
def change_tip_amount(request_id):
    help_request = HelpRequest.query.get_or_404(request_id) # Retrieve the help request with the given id from the database
    if help_request: #  if the help request exists
        post = help_request.post # Retrieve the relevant post
        tip_amount = request.json.get("tip_amount", 0.0) # Retrieve the delivery fee from the request JSON data
        if post.author == current_user: # if the current user is the author of the post - its a request for a lower delivery fee
            if help_request.is_waiting_tip_amount:
                return jsonify(message="Invalid action"), 400 # request to change delivery fee has already been sent
            try:
                tip_amount = float(tip_amount)
                if tip_amount <= 0:
                    raise ValueError()
            except (TypeError, ValueError):
                return jsonify(message="Invalid tip amount"), 400

            # Update the lower delivery fee (tip amount) and notify the sender
            help_request.lower_tip_amount=tip_amount
            db.session.commit()
            help_request.is_waiting_tip_amount=True
            db.session.commit()
            notification = Notification(content=current_user.first_name + " "+current_user.last_name +" offers you"
                                                                                                      " a different delivery fee",
                                endpoint='post', args = '{"post_id": ' + str(post.id) + '}',
                                user_id=help_request.sender.id, sender_id=current_user.id)
            send_notification(notification)
            return jsonify(message="change delivery fee request sent"), 200


        elif current_user==help_request.sender: #its a respose from the sender to the post author request for a lower delivery fee
            if not help_request.is_waiting_tip_amount: #if there is no request for a lower delivery fee, return error response
                return jsonify(message="Invalid action"), 400

            tip_amount = request.json.get("tip_amount")
            try:
                tip_amount = float(tip_amount)
                if tip_amount <= 0:
                    raise ValueError()
            except (TypeError, ValueError):
                return jsonify(message="Invalid tip amount"), 400

            if tip_amount==help_request.tip_amount: #sender did not change the delivery fee (tip amount)
                # Mark the request as not waiting for tip amount and notify the post author
                help_request.is_waiting_tip_amount = False
                db.session.commit()
                notification = Notification(
                    content=current_user.first_name + " " + current_user.last_name + " wants $"+str(tip_amount) +" for delivery",
                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                    user_id=post.author.id, sender_id=current_user.id)
                send_notification(notification)
                return jsonify(message="response sent successfully"), 200
            else: #sender changed the delivery fee (tip amount)
                help_request.tip_amount=tip_amount # Update the tip amount
                db.session.commit()
                # Mark the request as not waiting for tip amount and notify the post author
                help_request.is_waiting_tip_amount = False
                db.session.commit()

                notification = Notification(
                    content=current_user.first_name + " " + current_user.last_name + " wants $"+str(tip_amount) +" for delivery",
                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                    user_id=post.author.id, sender_id=current_user.id)
                send_notification(notification)
                return jsonify(message="tip amount updated successfully"), 200

    else:
        return jsonify(message="Invalid action"), 400



#This route allows the user to cancel a help request (delivery offer) for a post (product request).
# It handles the cancellation of the request (delivery offer) and provides appropriate response messages.
@app.route("/cancel_help_request/<int:post_id>", methods=["POST"])
@login_required
def cancel_help_request(post_id):
    help_request = current_user.get_help_request(post_id)

    if help_request:
        # Check if the current user is the sender of the request
        if help_request.sender != current_user:
            abort(403)  # Return a forbidden error if the user is not authorized

        # Delete the help request
        db.session.delete(help_request)
        db.session.commit()

        return jsonify({"message": "Request cancelled successfully"})
    else:
        return jsonify({"message": "Help request not found"}), 404



# This route hadles the accepting of a help request (delivery offer)
@app.route('/accept_help_request/<int:help_request_id>', methods=['POST'])
@login_required
def accept_help_request(help_request_id):
    help_request = HelpRequest.query.get_or_404(help_request_id)

    # Check if the current user is the author of the post
    if current_user != help_request.post.author:
        abort(403)  # Return a 403 Forbidden status if not authorized

    post=help_request.post
    if post.accepted_help_request_id:
        return jsonify(message="An accepted help request already exists for your request."), 400

    # Update the accepted flag in the database
    help_request.accepted = True

    if help_request.is_waiting_tip_amount:
        help_request.lower_tip_amount=None
        help_request.is_waiting_tip_amount=False
    db.session.commit()

    # Update the accepted_help_request_id of the post
    help_request.post.accepted_help_request_id = help_request.id
    db.session.commit()

    # notify the sender (of the delivery offer)
    notification = Notification(content=post.author.first_name+" " +post.author.last_name+" accepted your delivery offer",
                                endpoint='post', args = '{"post_id": ' + str(post.id) + '}',
                                user_id=help_request.sender.id, sender_id=current_user.id)
    send_notification(notification)

    return Response(status=200)



# This route handles the rejecting of a help request (delivery offer)
@app.route('/reject_help_request/<int:help_request_id>', methods=['POST'])
@login_required
def reject_help_request(help_request_id):
    help_request = HelpRequest.query.get_or_404(help_request_id)

    # Check if the current user is the author of the post
    if current_user != help_request.post.author:
        abort(403)  # Return a 403 Forbidden status if not authorized


    # Delete the request
    db.session.delete(help_request)
    db.session.commit()

    return Response(status=200)


#This route handles the end of a delivery process:
#if the current user is the recipient, it handles the confirmation of the delivery and rating the deliver
#if the current user is the deliver, it handles the arrival of the delivery and rating the recipient
@app.route("/send_review/<int:post_id>", methods=["POST"])
@login_required
def send_review(post_id): #user_id- the user that review was written for
    post = Post.query.get_or_404(post_id)
    if current_user==post.author:  # Review submission by the post's author (recipient)
        if not post.is_arrived: #delivery has not arrived yet
            abort(403)
        if post.is_arrived_confirmed: #delivery has arrived, deliver has already been rated.
            abort(403)
        rating = float(request.json.get("stars"))
        content = request.json.get("review_content", "")
        reviewer_id=post.author.id
        reviewed_id=post.accepted_help_request.sender.id
        review = Review(
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            content=content,
            is_deliver=True #post's author rate the deliver
        )
        db.session.add(review)
        db.session.commit()

        update_deliver_rating_attributes(reviewed_id, rating)

        post.is_arrived_confirmed=True #arrival has been confirmed
        db.session.commit()

        post.accepted_help_request.is_completed=True
        db.session.commit()

        #notify the deliver
        notification = Notification(content=post.author.first_name+" "+ post.author.last_name +" confirmed your delivery",
                                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                                    user_id=post.accepted_help_request.sender.id, sender_id=current_user.id)
        send_notification(notification)

        return jsonify(message="Review submitted successfully.")

    if current_user==post.accepted_help_request.sender: # Review submission by the deliver
        if post.is_arrived: #if author (recipient) has already been rated by deliver
            abort(403)
        rating = float(request.json.get("stars"))
        content = request.json.get("review_content", "")
        reviewer_id=post.accepted_help_request.sender.id
        reviewed_id=post.author.id
        review = Review(
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            content=content,
            is_recipient=True #deliver rates post's author
        )
        db.session.add(review)
        db.session.commit()

        post.is_arrived=True
        db.session.commit()

        # notify the recipient
        notification = Notification(content="Your delivery has arrived",
                                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                                    user_id=post.author.id, sender_id=current_user.id)
        send_notification(notification)

        return jsonify(message="Review submitted successfully.")
    abort(403)


#This route handles the cancellation of a delivery
@app.route("/cancel_delivery/<int:post_id>", methods=["POST"])
@login_required
def cancel_delivery(post_id): #user_id- the user that review was written for
    post = Post.query.get_or_404(post_id) #retrieve post from the database
    if current_user==post.author and post.accepted_help_request: #cancellation by recipient
        if post.is_arrived_confirmed: #delivery arrived, nothing to cancel !
            abort(403)
        if post.accepted_help_request.last_delivery_date.date()>=datetime.utcnow().date(): #check if the delivery date passed
            return jsonify({"message": "Delivery date hasn't expired yet"}), 404
        #if we got here, delivery date has expired, the recipient rate the deliver and cancel the delivery
        rating = float(request.json.get("stars"))
        content = request.json.get("review_content", "")
        reviewer_id=post.author.id
        reviewed_id=post.accepted_help_request.sender.id
        review = Review(
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            content=content,
            is_deliver=True
        )
        db.session.add(review)
        db.session.commit()

        update_deliver_rating_attributes(reviewed_id, rating)

        help_request = post.accepted_help_request
        help_request_sender_id = help_request.sender.id


        # mark help request as cancelled
        help_request.is_cancelled=True
        db.session.commit()

        #post is open to get new help requests
        post.accepted_help_request=None
        post.accepted_help_request_id=None
        post.is_arrived=False
        db.session.commit()

        #notify the deliver
        notification = Notification(content=post.author.first_name+" "+ post.author.last_name +" cancelled delivery",
                                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                                    user_id=help_request_sender_id, sender_id=current_user.id)
        send_notification(notification)

        return jsonify(message="Delivery was cancelled successfully.")

    elif post.accepted_help_request and current_user==post.accepted_help_request.sender:  #cancellation by deliver
        if post.is_arrived: #if delivery has been arrived, there is nothing to cancel !
            abort(403)
        #rate the recipient and cancel
        rating = float(request.json.get("stars"))
        content = request.json.get("review_content", "")
        reviewer_id = post.accepted_help_request.sender.id
        reviewed_id = post.author.id
        review = Review(
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            content=content,
            is_recipient=True  # deliver rates post's author
        )
        db.session.add(review)
        db.session.commit()

        help_request = post.accepted_help_request

        # mark help request as cancelled
        help_request.is_cancelled=True
        help_request.is_cancelled_by_deliver=True
        db.session.commit()

        #post is open to get new help requests
        post.current_cancelled_request_id=help_request.id
        post.accepted_help_request=None
        post.accepted_help_request_id=None
        post.is_arrived=False
        db.session.commit()

        #notify recipient
        notification = Notification(content=current_user.first_name+" "+ current_user.last_name +" cancelled delivery",
                                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                                    user_id=post.author.id, sender_id=current_user.id)
        send_notification(notification)

        return jsonify(message="Delivery was cancelled successfully.")


    abort(403)





#This route handles the delivery cancellation confirmation by the recipient:
#when deliver cancel the delivery, the recipient need to confirm and rate the deliver
@app.route("/confirm_cancelled_delivery/<int:post_id>", methods=["POST"])
@login_required
def confirm_cancelled_delivery(post_id):
    post=Post.query.get_or_404(post_id) #retrieve post (product request) from the database
    if current_user==post.author and post.current_cancelled_request_id:
        help_request=HelpRequest.query.get_or_404(post.current_cancelled_request_id) #retrieve the cancelled delivery offer from the database
        #rate the deliver
        rating = float(request.json.get("stars"))
        content = request.json.get("review_content", "")
        reviewer_id = post.author.id
        reviewed_id = help_request.sender.id
        review = Review(
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            content=content,
            is_deliver=True
        )
        db.session.add(review)
        db.session.commit()

        update_deliver_rating_attributes(reviewed_id, rating) #update deliver's node attributes on neo4j

        post.current_cancelled_request_id=None #now the recipient can accept new offers - they confirm the cancellation
        db.session.commit()

        help_request.accepted=False
        db.session.commit()

        #notify the deliver
        notification = Notification(content=post.author.first_name+" "+ post.author.last_name +" confirmed delivery cancellation",
                                    endpoint='post', args='{"post_id": ' + str(post.id) + '}',
                                    user_id=help_request.sender.id, sender_id=current_user.id)
        send_notification(notification)

        return jsonify(message="Delivery was cancelled successfully.")



#This route handles the serach for users
@app.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('query')  # Get the search query from the request arguments
    if query:
        query_parts = query.split()
        if len(query_parts) == 1:
            # Search for first name or last name
            users = User.query.filter(
                db.or_(
                    User.username.ilike(f'%{query}%'),  # Match username partially
                    User.first_name.ilike(f'%{query}%'),  # Match first name partially
                    User.last_name.ilike(f'%{query}%')  # Match last name partially
                )
            ).all()
        else:
            # Search for full name
            users = User.query.filter(
                db.and_(
                    User.first_name.ilike(f'%{query_parts[0]}%'),  # Match first name partially
                    User.last_name.ilike(f'%{query_parts[1]}%')  # Match last name partially
                )
            ).all()



        # Check if any results are found
        if not users:
            message = "No results found."
        else:
            message = ""

        # Render the search results template
        return render_template('search_results.html', users=users, query=query or "Random Results", message=message)

    else:
        # If no query is provided, do nothing
        return '',204




#This route marke notification as read when user click on the unread notification
@app.route('/notification/read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id):
    notification = Notification.query.get(notification_id)
    if notification and (not notification.is_read):
        if notification.user_id == current_user.id:  # Ensure the notification belongs to the current user
            # Mark the notification as read
            notification.is_read = True
            db.session.commit()

            # Decrement the unread_notifications count in User table
            current_user.unread_notifications_counter -= 1
            db.session.commit()

    return '', 204  # Return an empty response with 204 status code (No Content)


######################friends#############################################################


#This route handles the cancellation of a friend request that user send
@app.route("/cancel_friend_request/<int:recipient_id>", methods=["POST"])
@login_required
def cancel_friend_request(recipient_id):
    recipient=User.query.get(recipient_id) #get the user who got the friend request
    if recipient:
        if current_user.has_sent_friend_request(recipient): #if current user send him a friend request that has not been accepted yet
            current_user.cancel_friend_request(recipient.id) #cancel the friend request
            return jsonify({"message": "Request cancelled successfully"})
    else:
        return jsonify({"message": "friend request not found"}), 404




#This route handles the sending of a friend request
@app.route("/send_friend_request/<int:recipient_id>", methods=["POST"])
@login_required
def send_friend_request(recipient_id):
    recipient=User.query.get(recipient_id) #retrieve the recipient from the database
    if recipient: #make important validations before sending a friend request
        if recipient==current_user or current_user.has_sent_friend_request(recipient)\
                or  recipient.has_sent_friend_request(current_user) or current_user.are_friends(recipient):
            return jsonify(message="Invalid friend request"), 400

        current_user.send_friend_request(recipient.id) #send a friend reqeust

        #notify the recipient
        notification = Notification(content=current_user.first_name + " " + current_user.last_name + " sent you"
                                                                                                     " a friend request",
                                    endpoint='view_account', args = '{"username": "' + str(current_user.username) + '"}',
                                    user_id=recipient.id, sender_id=current_user.id)
        send_notification(notification)

        return jsonify(message="friend request has been sent successfully"), 200

    else: #no recipient
        return jsonify(message="Invalid friend request"), 400



#This route handles the accepting of a friend request
@app.route("/accept_friend_request/<int:sender_id>", methods=["POST"])
@login_required
def accept_friend_request(sender_id):
    sender=User.query.get(sender_id) #retrieve the sender from the database
    if sender and sender.has_sent_friend_request(current_user):
        if sender==current_user :
            return jsonify(message="Invalid action"), 400
        current_user.accept_friend_request(sender.id) #accept friend request

        #notify the sender
        notification = Notification(content=current_user.first_name + " " + current_user.last_name + " accepted your"
                                                                                                     " friend request",
                                    endpoint='view_account', args = '{"username": "' + str(current_user.username) + '"}',
                                    user_id=sender.id, sender_id=current_user.id)
        send_notification(notification)



        return jsonify(message="friend request has been accepted successfully"), 200
    else:
        return jsonify(message="Invalid action"), 400



#This route handles the rejecting of a friend request
@app.route("/reject_friend_request/<int:sender_id>", methods=["POST"])
@login_required
def reject_friend_request(sender_id):
    sender=User.query.get(sender_id) #retrieve the sender from the database
    if sender and sender.has_sent_friend_request(current_user):
        if sender==current_user :
            return jsonify(message="Invalid action"), 400
        current_user.reject_friend_request(sender.id) #reject friend request
        return jsonify(message="friend request has been rejected successfully"), 200
    else:
        return jsonify(message="Invalid action"), 400



# This route allows users to unfriend another user by canceling their friendship.
@app.route("/unfriend/<int:friend_id>", methods=["POST"])
@login_required
def unfriend(friend_id):
    friend=User.query.get(friend_id) #retrieve friend from the data base
    if friend and current_user.are_friends(friend): #validate that they are friends
        if friend==current_user :
            return jsonify(message="Invalid action"), 400
        current_user.unfriend(friend.id) #unfriend
        return jsonify(message="friendship has been cancelled successfully"), 200
    else:
        return jsonify(message="Invalid action"), 400





# -------- Google sing in ---------
# Set up the Google OAuth 2.0 provider
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id="883185021921-qk8ri4q21mhqd3qtr6idtb0fkb94ie2q.apps.googleusercontent.com",
    client_secret="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",
    access_token_url="https://oauth2.googleapis.com/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={
        "scope": "openid email profile",
        "prompt": "consent",
    },
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={
        "scope": "openid email profile",
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)


@app.route("/google_login")
def google_login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri, nonce="nonce")

@app.route("/authorize")
def authorize():

    token = google.authorize_access_token()
    #print(token)
    userinfo = google.parse_id_token(token, nonce="nonce")
    session["user_id"] = userinfo["sub"]
    session["user_email"] = userinfo["email"]
    session["first_name"] = userinfo["given_name"]
    session["last_name"] = userinfo["family_name"]
    session["user_name"] = userinfo["name"]
    session["picture"] = userinfo["picture"]

    user_id = session.get("user_id", None)
    user_email = session.get("user_email", None)
    user_name = session.get("user_name", None)
    first_name = session.get("first_name", None)
    last_name = session.get("last_name", None)
    user_name = session.get("user_name", None)
    user_picture = session.get("picture", None)
    if user_id is None:
        return redirect(url_for("login"))
    user = User.query.filter_by(google_id=user_id).first()
    if not user: # If the user doesn't exist, create a new user account
        return redirect(url_for('google_register', user_id=user_id, user_email=user_email, first_name=first_name, last_name=last_name))

    login_user(user)
    next_page = request.args.get('next')  # args is a dictionary. if next key does not exist, it returns none
    return redirect(next_page) if next_page else redirect(url_for('home'))

@app.route("/finishRegister", methods=['GET', 'POST'])
def google_register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    user_id = request.args.get('user_id')
    user_email = request.args.get('user_email')
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')


    form=GoogleRegistrationForm()

    if request.method == 'POST':  # Check if the request method is POST
        country_code = form.country.data
        country_name = pycountry.countries.get(alpha_2=country_code).name

        # Update the choices of the city field based on the selected country
        form.populate_city_choices(form.country.data)

    if form.validate_on_submit(): #if our form validated when it was submitted
        country_code = form.country.data
        country_name = pycountry.countries.get(alpha_2=country_code).name

        # generate unique username from email
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        username = user_email.split('@')[0]+random_string

        user = User(username=username, email=user_email,first_name=first_name, last_name=last_name,
                    is_google_user=True, google_id=user_id, country=country_name, city=form.city.data,
                    phone_code=form.phone_code.data, phone_number=form.phone_number.data)
        db.session.add(user)
        db.session.commit()

        # Create a corresponding node in Neo4j
        user.create_node_in_neo4j()

        login_user(user)
        next_page = request.args.get('next')  # args is a dictionary. if next key does not exist, it returns none
        return redirect(next_page) if next_page else redirect(url_for('home'))

    return render_template('google_register.html', title='Finish Register', form=form)


