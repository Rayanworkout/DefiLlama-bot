import tweepy

API_KEY = 'API_KEY'
API_KEY_SECRET = 'API_KEY'
ACCESS_TOKEN = 'API_KEY'
ACCESS_TOKEN_SECRET = 'API_KEY'

auth = tweepy.OAuthHandler(API_KEY, API_KEY_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)
