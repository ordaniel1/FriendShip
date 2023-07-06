import random
from friendship import app, db, bcrypt, neo4j_driver
from friendship.models import User, Post, Review
from PIL import Image
import os


#This function recommends friends to the current user based on friends of friends (FOFs) and Jaccard similarity.
#The top 20 recommendations are stored as recommended friend IDs in the user's node in the Neo4j database.
def recommend_friends_you_may_know(user_id):
    # Connect to Neo4j database
    session = neo4j_driver.session()

    num_friend_count_query = """
        MATCH (u:User)-[:Friend]->(:User)
        WHERE u.id = $user_id
        RETURN COUNT(*) AS friend_count
        """

    num_mutual_friend_count_query = """
        MATCH (u1:User {id: $user_id1})-[:Friend]-(f:User)-[:Friend]-(u2:User {id:  $user_id2})
        WHERE f.id <> $user_id1 AND f.id <> $user_id2
        RETURN COUNT(DISTINCT f) AS shared_friends_count
        """

    result = session.run(num_friend_count_query, user_id=user_id).single()
    user_friend_count = result["friend_count"]

    # find friend of friends
    friend_query = """

    MATCH (u:User)-[:Friend]-(f:User)-[:Friend]-(fof:User)
    WHERE u.id = $user_id AND NOT (u)-[:Friend]-(fof) AND fof.id <> $user_id
    RETURN DISTINCT fof.id AS fof_id
    """

    fof_results = session.run(friend_query, user_id=user_id)

    fof_scores = []
    for record in fof_results:
        fof_id = record["fof_id"]

        result = session.run(num_friend_count_query, user_id=fof_id).single()
        fof_friend_count=result["friend_count"]

        result=session.run(num_mutual_friend_count_query,user_id1=user_id, user_id2=fof_id).single()
        mutual_friend_count=result["shared_friends_count"]

        jaccard_similarity=mutual_friend_count/(fof_friend_count+user_friend_count-mutual_friend_count)


        fof_scores.append((fof_id, jaccard_similarity))

    # Sort friends based on weighted score
    fof_scores.sort(key=lambda x: x[1], reverse=True)

    # Get recommended friend IDs, limited to the first 20 (or fewer)
    recommended_friends = [fof_id for fof_id, _ in fof_scores[:20]]

    #save it on the node
    update_query = """
    MATCH (u:User {id: $user_id})
    SET u.recommended_friends = $recommended_friends
    """
    session.run(update_query, user_id=user_id, recommended_friends=recommended_friends)



def main():

    recommend_friends_you_may_know(202)




if __name__ == '__main__':
    main()








# some functions that helped us insert data for presentation


def generate_users():
    print("start creating user")
    first_names = [
        'Johnathan', 'Robert', 'James', 'William', 'David', 'Joseph', 'Charles', 'Thomas', 'Daniel', 'Matthew',
        'Donald', 'Anthony', 'Paula', 'Mark', 'George', 'Steven', 'Kenneth', 'Andrew', 'Edward', 'Brian',
        'Joshua', 'Kevin', 'Ronald', 'Timothy', 'Jason', 'Jeffrey', 'Frank', 'Gavin', 'Martin', 'Raymond',
        'Gregory', 'Eric', 'Jacob', 'Nathaniel', 'Bruno', 'Samuel', 'Patrick', 'Benjamin', 'Nicholas', 'Jack',
        'Dennis', 'Alexander', 'Mason', 'Jonathan', 'Will', 'Henry', 'Ryan', 'Zachary', 'Peter', 'Adam',
        'Walter', 'Nathan', 'Harold', 'Douglas', 'Arthur', 'Carl', 'Kenny', 'Roger', 'Lawrence', 'Stephen',
        'Terry', 'Jackson', 'Brandon', 'Joe', 'Albert', 'Billy', 'Ralph', 'Bobby', 'Johnny', 'Justin', 'Gerald',
        'Keith', 'Sam', 'Willie', 'Gerard', 'Louis', 'Steve', 'Wayne', 'Jeremy', 'Aaron', 'Randy', 'Howard',
        'Eugene', 'Carlos', 'Russell', 'Leonard', 'Graham', 'John', 'Nate', 'Paul', 'Harry', 'Franklin',
        'Bradley', 'Ernest', 'Jessica', 'Phillip', 'Simon', 'Alan', 'Shawn', 'Clarence', 'Fred', 'Philip',
        'Christian', 'Earl', 'Jimmy', 'Dan', 'Bryan', 'Luis', 'Tony', 'Andre', 'Ken', 'Juan', 'Jesse',
        'Ronnie', 'Bob', 'Mike', 'Jerry', 'Nicole', 'Nick', 'Logan', 'Craig', 'Gary', 'Scotty', 'Randall',
        'Joel', 'Richard', 'Jordan', 'Dylan', 'Troy', 'Victoria', 'Tyler', 'Sean', 'Kyle', 'Derrick', 'Darryl',
        'Kurt', 'Dustin', 'Claude', 'Lance', 'Danny', 'Sidney', 'Oscar', 'Barry', 'Julian', 'Max', 'Todd',
        'Frederick', 'Jeremiah', 'Ray', 'Leonardo', 'Charlie', 'Mitchell', 'Leo', 'Wesley', 'Terrance', 'Milton',
        'Ruben', 'Jared', 'Ricky', 'Victor', 'Chester', 'Clyde', 'Noah', 'Drew', 'Geoffrey', 'Neal', 'Karl',
        'Scott', 'Alfred', 'Ron', 'Lloyd', 'Stanley', 'Gabriel', 'Rick', 'Shane', 'Roy', 'Jorge', 'Freddie',
        'Dave', 'Dean', 'Lester', 'Marcus', 'Seth', 'Brad', 'Maurice', 'Chris', 'Jim', 'Glen', 'Lucas', 'Jennifer',
        'Ariel', 'Debby', 'Amanda', 'Mathew', 'Austin', 'Barbara', 'Lionel', 'Ben', 'Taylor', 'Garrett'
    ]

    last_names = [
        'Smith', 'Johnson', 'Williams', 'Jones', 'Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor',
        'Anderson', 'Thomas', 'Jackson', 'White', 'Harris', 'Martin', 'Thompson', 'Garcia', 'Martinez', 'Robinson',
        'Clark', 'Rodriguez', 'Lewis', 'Lee', 'Walker', 'Hall', 'Allen', 'Young', 'Hernandez', 'King', 'Wright',
        'Lopez', 'Hill', 'Scott', 'Green', 'Adams', 'Baker', 'Gonzalez', 'Nelson', 'Carter', 'Mitchell', 'Perez',
        'Roberts', 'Turner', 'Phillips', 'Campbell', 'Parker', 'Evans', 'Edwards', 'Collins', 'Stewart', 'Sanchez',
        'Morris', 'Rogers', 'Reed', 'Cook', 'Morgan', 'Bell', 'Murphy', 'Bailey', 'Rivera', 'Cooper', 'Richardson',
        'Cox', 'Howard', 'Ward', 'Torres', 'Peterson', 'Gray', 'Ramirez', 'James', 'Watson', 'Brooks', 'Kelly',
        'Sanders', 'Price', 'Bennett', 'Wood', 'Barnes', 'Ross', 'Henderson', 'Coleman', 'Jenkins', 'Perry',
        'Powell', 'Long', 'Patterson', 'Hughes', 'Flores', 'Washington', 'Butler', 'Simmons', 'Foster', 'Gonzales',
        'Bryant', 'Alexander', 'Russell', 'Griffin', 'Diaz', 'Hayes', 'Myers', 'Ford', 'Hamilton', 'Graham',
        'Sullivan', 'Wallace', 'Woods', 'Cole', 'West', 'Jordan', 'Owens', 'Reynolds', 'Fisher', 'Ellis', 'Harrison',
        'Gibson', 'Mcdonald', 'Cruz', 'Marshall', 'Ortiz', 'Gomez', 'Murray', 'Freeman', 'Wells', 'Webb', 'Simpson',
        'Stevens', 'Tucker', 'Porter', 'Hunter', 'Hicks', 'Crawford', 'Henry', 'Boyd', 'Mason', 'Morales',
        'Kennedy', 'Warren', 'Dixon', 'Ramos', 'Reyes', 'Burns', 'Gordon', 'Shaw', 'Holmes', 'Rice', 'Robertson',
        'Hunt', 'Black', 'Daniels', 'Palmer', 'Mills', 'Nichols', 'Grant', 'Knight', 'Ferguson', 'Rose', 'Stone',
        'Hawkins', 'Dunn', 'Perkins', 'Hudson', 'Spencer', 'Gardner', 'Stephens', 'Payne', 'Pierce', 'Berry',
        'Matthews', 'Arnold', 'Wagner', 'Willis', 'Ray', 'Watkins', 'Olson', 'Carroll', 'Duncan', 'Snyder', 'Hart',
        'Cunningham', 'Bradley', 'Lane', 'Andrews', 'Ruiz', 'Harper', 'Fox', 'Riley', 'Armstrong', 'Carpenter',
        'Weaver', 'Greene', 'Lawrence', 'Elliott', 'Chavez', 'Sims', 'Austin', 'Peters', 'Kelley', 'Franklin',
        'Lawson', 'Fields', 'Gutierrez', 'Ryan', 'Schmidt', 'Carr', 'Vasquez', 'Castillo', 'Wheeler', 'Chapman',
        'Oliver', 'Montgomery', 'Richards', 'Williamson', 'Johnston', 'Banks', 'Meyer', 'Bishop', 'Mccoy', 'Howell',
        'Alvarez', 'Morrison', 'Hansen', 'Fernandez', 'Garza', 'Harvey', 'Little', 'Burton', 'Stanley', 'Nguyen',
        'George', 'Jacobs', 'Reid', 'Kim', 'Fuller', 'Lynch', 'Dean', 'Gilbert', 'Garrett', 'Romero', 'Welch',
        'Larson', 'Frazier', 'Burke', 'Hanson', 'Day', 'Mendoza', 'Moreno', 'Bowman', 'Medina', 'Fowler', 'Brewer',
        'Hoffman', 'Carlson', 'Silva', 'Pearson', 'Holland', 'Douglas', 'Fleming', 'Jensen', 'Vargas', 'Byrd',
        'Davidson', 'Hopkins', 'May', 'Terry', 'Herrera', 'Wade', 'Soto', 'Walters', 'Curtis', 'Neal', 'Caldwell',
        'Lowe', 'Jennings', 'Barnett', 'Graves', 'Jimenez', 'Horton', 'Shelton', 'Barrett', 'Obrien', 'Castro',
        'Sutton', 'Gregory', 'Mckinney', 'Lucas', 'Miles', 'Craig', 'Rodriquez', 'Chambers', 'Holt', 'Lambert',
        'Fletcher', 'Watts', 'Bates', 'Hale', 'Rhodes', 'Pena', 'Beck', 'Newman', 'Haynes', 'Mcdaniel', 'Mendez',
        'Bush', 'Vaughn', 'Parks', 'Dawson', 'Santiago', 'Norris', 'Hardy', 'Love', 'Steele', 'Curry', 'Powers',
        'Schultz', 'Barker', 'Guzman', 'Page', 'Munoz', 'Ball', 'Keller', 'Chandler', 'Weber', 'Leonard', 'Walsh',
        'Lyons', 'Ramsey', 'Wolfe', 'Schneider', 'Mullins', 'Benson', 'Sharp', 'Bowen', 'Daniel', 'Barber', 'Cummings'
    ]

    cities = [
        'Tel Aviv', 'Jerusalem', 'Haifa', 'Rishon LeZion', 'Petah Tikva', 'Ashdod', 'Netanya', 'Beer Sheva',
        'Bnei Brak', 'Holon', 'Ramat Gan', 'Givatayim', 'Bat Yam', 'Ashkelon', 'Herzliya', 'Kfar Saba', 'Raanana',
        'Ramat HaSharon',
        'Nahariya', 'Lod'
    ]

    for i in range(200):
        first_name = first_names[i]
        last_name = last_names[i]
        hashed_password = bcrypt.generate_password_hash('12345678').decode('utf-8')
        username = first_name + "_" + last_name
        email = username + "@gmail.com"
        country = "Israel"
        city = random.choice(cities)
        phone_code = "972"
        phone_number = "0525555555"
        image_file = "profile_pic(" + str(i + 1) + ").jpg"
        user = User(username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=hashed_password,
                    country=country,
                    city=city,
                    phone_code=phone_code,
                    phone_number=phone_number,
                    image_file=image_file)

        db.session.add(user)
        db.session.commit()
        user.create_node_in_neo4j()

    with neo4j_driver.session() as session:
        # Iterate over each user and set the ratings
        for user_id in range(1, 201):
            rating_as_deliver = round(random.uniform(0, 5), 1)
            reviews_deliver_counter = random.randint(2, 100)
            # Execute a Cypher query to update the user with the ratings
            query = """
                MATCH (u:User {id: $user_id})
                SET u.rating_as_deliver = $rating_as_deliver, u.reviews_deliver_counter = $reviews_deliver_counter
                """
            session.run(query, user_id=user_id, rating_as_deliver=rating_as_deliver,
                        reviews_deliver_counter=reviews_deliver_counter)


def generate_friendships():
    # run this query few times(13-15), using neo4j
    create_friendships_query = """ 
        MATCH (u1:User), (u2:User)
        WHERE u1.id <> u2.id AND u1.country = "Israel" AND u2.country = "Israel"
        AND rand() < 0.3  // Adjust the probability of friendship creation
        WITH u1, u2
        ORDER BY rand()
        LIMIT 201  // Adjust the number of pairs to be selected randomly
        MERGE (u1)-[:Friend]->(u2)
        MERGE (u2)-[:Friend]->(u1)  // Add this line to create a mutual friendship
            """

    with neo4j_driver.session() as session:
        session.run(create_friendships_query)


def resize():
    original_dir = 'friendship/static/big_pictures'
    resized_dir = 'friendship/static/profile_pics'
    # Ensure the resized directory exists
    os.makedirs(resized_dir, exist_ok=True)
    # Iterate over the original images
    for filename in os.listdir(original_dir):
        if filename.endswith('.jpg') or filename.endswith('.png'):
            # Open the original image
            image = Image.open(os.path.join(original_dir, filename))

            # Resize the image to 125x125
            resized_image = image.resize((125, 125))

            # Save the resized image
            resized_image.save(os.path.join(resized_dir, filename))

    print('Resizing complete!')


def insertPosts():
    productNames = ["Apple iPhone 13 Pro", "Canon EOS R5 Mirrorless Camera", "Rolex Submariner Date Watch",
                    "Chanel Classic Flap Bag", "Louis Vuitton Josh Backpack", "Gucci Ace Sneakers",
                    "Sony PlayStation 5", "Dyson Supersonic Hair Dryer", "Hermes Birkin Bag",
                    " Nintendo Switch Console", "Samsung Galaxy S21 Ultra", "Chanel N°5 Perfume",
                    "Swiss Army Knife", " Turkish Delight Assortment", "K-beauty Skincare Set (Dr Jart)",
                    "Montblanc Meisterstück Fountain Pen", "Italian Leather Shoes", "Belgian Chocolates Assortment",
                    "Persian small Rug", "Japanese Matcha Tea Set", " Scottish Single Malt Whisky",
                    "Dutch Delftware", " Swiss Chocolate Selection", "Australian Opal Necklace",
                    "Thai Silk Scarf", "Brazilian Havaianas Flip-Flops", " Indian Spices Assortment",
                    "Greek Olive Oil", "Vietnamese Silk Lantern", "Peruvian Alpaca Sweater",
                    "Mama Scrub Sponge Set", "Turkish Evil Eye Talisman", "German Beer Stein",
                    "Mexican Handwoven Blanket", "Bodysea Perfume for man", "Leather Wallet",
                    "Moroccan Argan Oil", "Irish Whiskey", "Japanese Kimono Robe", ]

    countries = ["United States", "Japan", "Switzerland",
                 "France", "France", "Italy",
                 "United States", "United Kingdom", "France",
                 "Japan", "South Korea", "France",
                 "Switzerland", "Turkey", "China",
                 "Germany", "Italy", "Belgium",
                 "Jordan", "Japan", "United Kingdom",
                 "Netherlands", "Switzerland", "Australia",
                 "Thailand", "Brazil", "India",
                 "Greece", "Viet Nam", "Peru",
                 "United States", "Turkey", "Germany",
                 "Mexico", "France", "Italy",
                 "Morocco", "Ireland", "Japan"]

    choices = ['$0 - $20', '$20 - $50', '$50 - $100', '$100 - $200', '$200 - $500', '$500+']

    prices = [None, None, None,
              None, 2500.0, None,
              499.0, 399.0, None,
              299.0, None, None,
              None, None, None,
              None, None, None,
              None, None, None,
              None, None, None,
              None, None, None,
              None, None, None,
              None, None, None,
              None, None, None,
              None, None, None]

    price_ranges = ['$500+', '$500+', '$500+',
                    '$500+', '$500+', '$500+',
                    '$200 - $500', '$200 - $500', '$500+',
                    '$200 - $500', '$500+', '$100 - $200',
                    '$20 - $50', '$0 - $20', '$50 - $100',
                    '$200 - $500', '$200 - $500', '$20 - $50',
                    '$500+', '$0 - $20', '$100 - $200',
                    '$100 - $200', '$20 - $50', '$200 - $500',
                    '$0 - $20', '$0 - $20', '$0 - $20',
                    '$20 - $50', '$0 - $20', '$50 - $100',
                    '$0 - $20', '$0 - $20', '$20 - $50',
                    '$0 - $20', '$100 - $200', '$200 - $500',
                    '$0 - $20', '$50 - $100', '$50 - $100']

    tips = [75.0, 100.0, 250.0,
            150.0, 80.0, 50.0,
            30.0, 20.0, 380.0,
            20.0, 35.0, 15.0,
            8.0, 5.0, 15.0,
            30.0, 25.0, 7.0,
            75.0, 5.0, 20.0,
            20.0, 5.0, 25.0,
            3.0, 4.0, 4.0,
            5.0, 3.0, 15.0,
            4.0, 4.0, 8.0,
            4.0, 16.0, 35.0,
            5.0, 10.0, 10.0]

    contents = [
        "I know it's available in Israel, but it's much cheaper abroad. Can you please purchase the iPhone 13 Pro (256GB, Purple) for me? I prefer the US version as it supports FaceTime.",
        "Please ensure it's the body only without any additional lenses.",
        "Looking for the black dial version, stainless steel bracelet.",
        "I've always dreamed of owning a Chanel Classic Flap Bag in black leather with gold hardware. It's a bit pricier in Israel, so I'm hoping you can grab it for me while you're in France!",
        "The product can be bought at various Louis Vuitton branches. I want the brown version, product number: M45369. Please wrap it as a gift if possible.",
        "Looking for the white leather version with the bee embroidery, size US 9 / EU 43.",
        "Please check for availability and bundle options",
        "The product can be found at various authorized Dyson retailers. Looking for the silver/pink version.",
        "I've always admired the Hermes Birkin Bag in Togo leather. Please inquire about available colors and share the options with me.",
        "Please check for availability and include a game recommendation",
        "I'm looking for the Samsung Galaxy S21 Ultra (256GB, Phantom Black / White) in the South Korean version only. Please ensure it's unlocked and compatible with international networks.",
        "I'd love to get the classic Chanel N°5 Perfume in a 100ml bottle. 150ml is also ok.",
        "I'm interested in a genuine Swiss Army Knife, preferably with multiple tools. It would be a great gift for my adventurous friend.",
        "Missing my last holiday in Turkey. I  am obsessed with the original Turkish Delight, I must eat that again.",
        "I'm a huge fan of K-beauty products. Could you put together a skincare set with popular Korean brands like Innisfree, Etude House, and Laneige? Don't forget the sheet masks!",
        "I've always admired the elegance of Montblanc Meisterstück Fountain Pens. If you come across a reputable retailer, please grab one for me.",
        "I'm on the lookout for a pair of high-quality Italian leather shoes, preferably handmade. Size 9 (EU 43).",
        "Belgian chocolates are renowned for their rich and indulgent flavors. Please pick up a box of assorted chocolates for me to savor.",
        "I'm in love with the intricate designs of Persian rugs. If you stumble upon a reputable rug dealer in Jordan / Turkey, please help me choose a beautiful piece for my home.",
        "I'm a tea enthusiast, and I've heard that Japanese Matcha tea is exceptional. Please find me a traditional Matcha tea set, including a bowl, whisk, and powdered Matcha tea.",
        "I'm looking for a fine bottle of Scottish single malt whisky to add to my collection. It would be great if you can recommend a distinctive and aged whisky.",
        "I've always admired the beauty of Dutch Delftware pottery. If you come across any hand-painted ceramic pieces, particularly blue and white designs, please grab them for me.",
        "Swiss chocolates are known for their exceptional quality and craftsmanship. Please select a variety of Swiss chocolate bars and truffles for me to enjoy.",
        "I've always been fascinated by the beauty of Australian opals. If you find a reputable jeweler offering opal rings or earrings, please consider purchasing them for me.",
        "Thai silk is renowned for its vibrant colors and luxurious texture. I'd love to have a Thai silk scarf to add a touch of elegance to my outfits.",
        "Havaianas flip-flops are known for their comfort and style. If you come across any Havaianas stores, please help me pick out a couple of pairs in different colors.",
        "Indian spices add incredible flavors to dishes. Please get me a selection of authentic Indian spices like turmeric, cumin, cardamom, and garam masala.",
        "Greek olive oil is renowned for its superior quality. Please bring me a bottle of extra virgin olive oil made from Koroneiki olives.",
        "Vietnamese silk lanterns are exquisite decorative items. I'd love to have a vibrant and handcrafted lantern to brighten up my living space.",
        "I've heard that Peruvian alpaca sweaters are incredibly soft and warm. If you find a shop selling authentic alpaca sweaters, please help me choose a cozy one.",
        "I've heard great things about the Mama scrub sponge set from the United States. If you come across this set, please grab one for me.",
        "I'm looking for an authentic Turkish Evil Eye talisman, believed to bring good luck and ward off evil. It can be a small pendant or a decorative item.",
        "A traditional German beer stein would make a great addition to my collection. I prefer a hand-painted design with intricate details.",
        "I'm in love with the vibrant colors and patterns of Mexican handwoven blankets. If you find a local artisan selling these blankets, please get one for me.",
        "France is famous for its exquisite perfumes. If you find a boutique fragrance store offering a unique French perfume, I'd love to add it to my collection.",
        "I'm in need of a new leather wallet from YSL, black with golden monogram",
        "Moroccan argan oil is known for its nourishing properties for hair and skin. If you come across a reputable seller offering pure argan oil, please get a bottle for me.",
        "I'm a whiskey enthusiast, and I've heard that Irish whiskey has a unique flavor profile. If you find a bottle of premium Irish whiskey, please consider purchasing it for me.",
        "I've always admired the elegance of Japanese kimono robes. If you find a shop selling authentic kimono robes, please help me choose a beautiful design."]

    authors_id = [104, 73, 112, 201, 13, 42,  # john smith friends
                  151, 153, 201, 20, 46, 30,
                  104, 73, 201, 112, 13, 42,
                  194, 47, 201, 23, 159, 89,  # Marco polo friends
                  111,
                  201, 201, 201, 201, 201,  # john smith closed/in process posts
                  202, 202, 202, 202, 202]  # marco polo posts

    # lets insert onlyfirst 35
    for i in range(35):
        product_name = productNames[i]
        content = contents[i]
        user_id = authors_id[i]
        country = countries[i]
        price = prices[i]
        price_range = price_ranges[i]
        tip_amount = tips[i]
        image_file = "image" + str(i + 1) + ".png"
        if price:
            post = Post(product_name=product_name,
                        content=content,
                        user_id=user_id,
                        country=country,
                        price=price,
                        price_range=price_range,
                        tip_amount=tip_amount,
                        image_file=image_file
                        )
        else:
            post = Post(product_name=product_name,
                        content=content,
                        user_id=user_id,
                        country=country,
                        price_range=price_range,
                        tip_amount=tip_amount,
                        image_file=image_file
                        )

        db.session.add(post)
        db.session.commit()




def insertMarcoReviews():
    rates_for_marco = [5.0, 5.0, 5.0, 4.5, 4.5,
                       4.5, 4.5, 4.5, 4.5, 4.5,
                       4.5, 5.0, 5.0, 4.5, 4.5,
                       4.5, 4.5]

    content_for_marco = [
        "Marco provided an excellent delivery service. He was punctual, professional, and handled my package with care.",
        "He delivered my order on time and with a friendly attitude. I definitely choose him again for future deliveries.",
        "He went above and beyond to ensure my package arrived safely and on time.",
        "Great experience with Marco as my delivery person. He was courteous,highly recommended.",
        "Marco is an amazing. He communicates well and provides updates. I'm happy with his service.",
        "I had a positive experience with Marco. He delivered my package promptly and handled it with care.",
        "Marco exceeded my expectations as a delivery person. He was friendly, responsive. I'm impressed.",
        "I'm pleased with Marco's delivery service. He was reliable, and my package arrived in excellent condition.",
        "Marco is a trustworthy delivery person. He handled my fragile items with care.",
        "I'm grateful for Marco's delivery service. He was punctual, friendly. I'm satisfied.",
        "Marco provided a smooth delivery experience. He was professional and delivered my items on time.",
        "I highly recommend Marco for deliveries. He handled my package with care and delivered it promptly.",
        "Marco is a reliable delivery person. He was responsive to my inquiries and delivered my package on time.",
        "I had a great experience with Marco. He was polite and delivered my items in perfect condition.",
        "Marco provided excellent delivery service. He was professional and punctual.",
        "I'm satisfied with Marco's delivery service. He handled my package carefully and delivered it on time.",
        "Marco is a dependable delivery person. He kept me updated throughout the delivery process.",
        # Add more reviews here
    ]

    reviewer_ids = [194, 47, 23, 159, 89,
                    98, 42, 47, 23, 159,
                    146, 106]

    for i in range(12):
        reviewer_id = reviewer_ids[i]
        reviewed_id = 202
        rating = rates_for_marco[i]
        content = content_for_marco[i]
        is_deliver = True
        review = Review(reviewer_id=reviewer_id,
                        reviewed_id=reviewed_id,
                        rating=rating,
                        content=content,
                        is_deliver=is_deliver
                        )

        db.session.add(review)
        db.session.commit()



