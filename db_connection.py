from pymongo.mongo_client import MongoClient

uri = "mongodb+srv://jinyoonok:wlsdbs981023@cmpsc487-jinyoon.vuymlgv.mongodb.net/?retryWrites=true&w=majority"
db_name = 'CMPSC487-Project3'

def get_db_connection():
    """
    Connects to the MongoDB and returns the specified collection.
    Returns:
    - collection: The MongoDB collection object
    """
    client = MongoClient(uri)
    db = client[db_name]
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        # Optionally, add a line here to test interaction with your collection, like finding a document
        # Example: print(collection.find_one({}))
    except Exception as e:
        print(e)
    return db