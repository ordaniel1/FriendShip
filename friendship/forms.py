from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed #fileAllowed -  a "validator"
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, SelectField, FloatField
from wtforms.validators import DataRequired, length, Email, EqualTo, ValidationError, InputRequired, NumberRange, Optional
from friendship.models import User
import pycountry
import phonenumbers
import requests


# This function retrieves a list of phone codes for different countries.
# It uses the pycountry and phonenumbers libraries to iterate over countries,
# retrieve the country code, and format the country name with the code.
# The function returns the list of phone codes.
def get_phone_codes():
    phone_codes = []
    for country in pycountry.countries:
        country_code = phonenumbers.country_code_for_region(country.alpha_2)
        phone_codes.append((country_code, f"{country.name} (+{country_code})"))
    return phone_codes



#The RegistrationForm class represents a form for user registration in the app
class RegistrationForm(FlaskForm):
    username=StringField('Username',
                         validators=[DataRequired(), length(min=2, max=20)]) #Username will be the label in our html
                                                    # #validators is a list of validation that we want to check

    email = StringField('Email',
                        validators=[DataRequired(),Email()])

    first_name=StringField('First Name',
                         validators=[DataRequired(), length(max=30)])
    last_name=StringField('Last Name',
                         validators=[DataRequired(), length(max=30)])

    password = PasswordField('Password', validators=[DataRequired(),  length(min=8, max=20)])

    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')]) #the *field* password

    country = SelectField('Country', choices=[('', '-Select a Country-')]+[(country.alpha_2, country.name) for country in pycountry.countries],
                          validators=[InputRequired()])
    city = SelectField('City', choices=[], validators=[InputRequired()])


    phone_code = SelectField('Phone Number', choices=[('', '-Select-')]+ get_phone_codes(), validators=[InputRequired()])


    phone_number = StringField('', validators=[DataRequired(), length(min=7, max=20)])


    submit= SubmitField('Sign Up')

    #validation functions - will be called inside the implemetation of validate_on_submit() that is used in routes.py:
    def validate_username(self, username):
        # check if username already exists in db
        user = User.query.filter_by(username=username.data).first()
        if user: #if user with that username already exists
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        # check if username already exists in db
        user = User.query.filter_by(email=email.data).first()
        if user: #if user already exists
            raise ValidationError('That email is taken. Please choose a different one.')

    def validate_phone_number(self, field):
        phone_code = self.phone_code.data
        phone_number = field.data
        number = "+" + phone_code + phone_number

        try:
            parsed_number = phonenumbers.parse(number)
            if not phonenumbers.is_possible_number(parsed_number) or not phonenumbers.is_valid_number(parsed_number):
                raise ValidationError('That phone number is invalid. Please enter a valid phone number.')
        except phonenumbers.NumberParseException:
            raise ValidationError('Invalid phone number format. Please enter a valid phone number.')

    def populate_city_choices(self, country_code):
        api_username = 'ordaniel1'  # Replace with your GeoNames username
        base_url = 'http://api.geonames.org/searchJSON'
        params = {
            'country': country_code,
            'maxRows': 1000,
            'username': api_username
        }

        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            city_choices = [(city['name'], city['name']) for city in data['geonames']]
            self.city.choices = city_choices
        else:
            self.city.choices = []




# The GoogleRegistrationForm class represents a form for users registering with their Google account,
# requiring them to provide additional information such as country, city, phone code,
# and phone number to complete the registration process.
class GoogleRegistrationForm(FlaskForm):
    country = SelectField('Country', choices=[('', '-Select a Country-')]+[(country.alpha_2, country.name) for country in pycountry.countries],
                          validators=[InputRequired()])
    city = SelectField('City', choices=[], validators=[InputRequired()])

    phone_code = SelectField('Phone Number', choices=[('', '-Select-')]+ get_phone_codes(), validators=[InputRequired()])

    phone_number = StringField('', validators=[DataRequired(), length(min=7, max=20)])

    submit= SubmitField('Start !')

    def populate_city_choices(self, country_code):
        api_username = 'ordaniel1'  # Replace with your GeoNames username
        base_url = 'http://api.geonames.org/searchJSON'
        params = {
            'country': country_code,
            'maxRows': 1000,
            'username': api_username
        }

        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            city_choices = [(city['name'], city['name']) for city in data['geonames']]
            self.city.choices = city_choices
        else:
            self.city.choices = []

    def validate_phone_number(self, field):
        phone_code = self.phone_code.data
        phone_number = field.data
        number = "+" + phone_code + phone_number

        try:
            parsed_number = phonenumbers.parse(number)
            if not phonenumbers.is_possible_number(parsed_number) or not phonenumbers.is_valid_number(parsed_number):
                raise ValidationError('That phone number is invalid. Please enter a valid phone number.')
        except phonenumbers.NumberParseException:
            raise ValidationError('Invalid phone number format. Please enter a valid phone number.')


#The LoginForm class represents a form for user login
class LoginForm(FlaskForm):

    email = StringField('Email',
                        validators=[DataRequired(),Email()])

    password = PasswordField('Password', validators=[DataRequired(),  length(min=8, max=20)])

    remember =BooleanField('Remember Me')
    submit= SubmitField('Login')




#The UpdateAccountForm class represents a form for updating user account information
class UpdateAccountForm(FlaskForm): #update password will not be here
    first_name=StringField('First Name',validators=[DataRequired(), length(max=30)])

    last_name=StringField('Last Name',validators=[DataRequired(), length(max=30)])

    username=StringField('Username',
                         validators=[DataRequired(), length(min=2, max=20)]) #Username will be the label in our html
                                                    # #validators is a list of validation that we want to check

    email = StringField('Email',
                        validators=[DataRequired(),Email()])

    country = SelectField('Country', choices=[('', '-Select a Country-')]+[(country.alpha_2, country.name) for country in pycountry.countries],
                          validators=[InputRequired()])
    city = SelectField('City', choices=[], validators=[InputRequired()])


    phone_code = SelectField('Phone Number', choices=[('', '-Select-')]+ get_phone_codes(), validators=[InputRequired()])

    phone_number = StringField('', validators=[DataRequired(), length(min=7, max=20)])


    picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit= SubmitField('Update')

    #validation functions - will be called inside the implemetation of validate_on_submit() that is used in routes.py:
    def validate_username(self, username):
        if username.data != current_user.username:
            # check if username already exists in db
            user = User.query.filter_by(username=username.data).first()
            if user: #if user with that username already exists
                raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        if email.data != current_user.email:
            # check if username already exists in db
            user = User.query.filter_by(email=email.data).first()
            if user: #if user already exists
                raise ValidationError('That email is taken. Please choose a different one.')

    def populate_city_choices(self, country_code):
        api_username = 'ordaniel1'  # Replace with your GeoNames username
        base_url = 'http://api.geonames.org/searchJSON'
        params = {
            'country': country_code,
            'maxRows': 1000,
            'username': api_username
        }

        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            city_choices = [(city['name'], city['name']) for city in data['geonames']]
            self.city.choices = city_choices
        else:
            self.city.choices = []

    def validate_phone_number(self, field):
        phone_code = self.phone_code.data
        phone_number = field.data
        number = "+" + phone_code + phone_number

        try:
            parsed_number = phonenumbers.parse(number)
            if not phonenumbers.is_possible_number(parsed_number) or not phonenumbers.is_valid_number(parsed_number):
                raise ValidationError('That phone number is invalid. Please enter a valid phone number.')
        except phonenumbers.NumberParseException:
            raise ValidationError('Invalid phone number format. Please enter a valid phone number.')





#The PostForm class represents a form for creating a new product request (post)
class PostForm(FlaskForm):
    product_name = StringField('Product Name', validators=[DataRequired()]) #DataRequired because every post has to have a title
    country = SelectField('Country', choices=[('', '-Select a Country-')]+[(country.name, country.name) for country in pycountry.countries],
                          validators=[InputRequired()])
    price = FloatField('Price (USD)',  validators=[Optional(), NumberRange(min=0)])
    price_range = SelectField('Price Range',validators=[Optional()], choices=[('', '-Select a Price Range-'), ('$0 - $20', '$0 - $20'), ('$20 - $50', '$20 - $50'), ('$50 - $100', '$50 - $100'), ('$100 - $200', '$100 - $200'), ('$200 - $500', '$200 - $500'), ('$500+', '$500+')])
    tip_amount = FloatField('Delivery Fee (USD)', validators=[DataRequired(),NumberRange(min=0)])
    content = TextAreaField('Content', validators=[DataRequired(), length(max=140)])
    picture = FileField('Add/Update a Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Post')

    def validate_price(self, field):
        print("validation")
        price = self.price.data
        price_range = field.data
        if not price_range and not price:
            raise ValidationError('Please enter a specific price or choose a price range.')


#################END OF FILE######################################################################################

#IGNORE IT - WE DID NOT USE IT
class SendRequestForm(FlaskForm):
    tip_amount = FloatField('Delivery Tip Amount (USD)', validators=[InputRequired(), NumberRange(min=0, message='Please enter a valid tip amount.')])
    submit = SubmitField('Send Request')



