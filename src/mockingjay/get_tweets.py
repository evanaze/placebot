"""Get tweets for a specified user."""
# Third party packages
import tweepy

# Internal packages
from src.mockingjay.db_conn import DbConn
from src.mockingjay.logger import get_logger
from src.mockingjay.utils import check_handles
from src.mockingjay.process import process_tweets
from src.mockingjay.twitter_conn import TwitterConn


LOGGER = get_logger(__name__)


class TweetReader(TwitterConn):
    def __init__(self, usernames: list[str] = ["PIaceboAddict"]) -> None:
        """Read the tweets from a user or set of users.

        :param usernames: The list of usernames to scrape tweets for.
        """
        super().__init__()
        self.usernames = usernames
        self.since = None
        self.db_conn = DbConn()

    def get_user_ids(self) -> None:
        """Get the user IDs of the users Twitter handles from Tweepy"""
        self.user_ids = {}
        for username in self.usernames:
            # Get the current author ID from Tweepy
            user = self.tweepy_client.get_user(username=username)
            # Check for errors in finding the user
            if user.errors:
                msg = user.errors[0]["detail"]
                raise UserNotFoundError(msg)

    def check_newer_tweets(self) -> bool:
        """Check if the user has newer tweets we can scrape.

        :return: A boolean value for whether or not there are new tweets to scrape.
        """
        # Get the most recent tweet from our database
        most_recent_db = self.db_conn.get_most_recent_tweet(self.author_id)
        LOGGER.debug(f"Most recent recorded tweet: {most_recent_db}")
        # Get the user's most recent tweet on Twitter
        most_recent_tweets = self.tweepy_client.get_users_tweets(
            id=self.author_id,
            exclude=["retweets", "replies"],
            since_id=most_recent_db,
            max_results=5,
        )
        # Check if there are new tweets
        return int(most_recent_tweets.meta["result_count"]) != 0

    def get_users_tweets(self) -> None:
        """Get the user's tweets."""
        msg = f"Getting tweets for user {self.username}"
        if self.since:
            msg += f" since tweet {self.since}"
        LOGGER.debug(msg)
        # Get tweets, optionally after a tweet ID
        self.tweets = []
        for tweet in tweepy.Paginator(
            self.tweepy_client.get_users_tweets,
            id=self.author_id,
            exclude=["retweets", "replies"],
            since_id=self.since,
        ).flatten():
            self.tweets.append(tweet)

    def get_tweets(self) -> None:
        """Get all tweets for the data set."""
        # Get user ID's
        self.user_ids = check_handles(self.usernames)
        for self.username in self.user_ids:
            self.author_id = self.user_ids[self.username]
            # Check for existing tweet data for the user in our database
            if self.db_conn.check_existing_tweets(self.author_id):
                LOGGER.debug(
                    f"Found existing tweets in the database for user {self.username}"
                )
                # Check if the user has made new tweets we can scrape
                if self.check_newer_tweets():
                    LOGGER.info(f"New tweets for user {self.username}")
                    self.get_users_tweets()
                else:
                    LOGGER.info(f"No new tweets to scrape for user {self.username}")
                    continue
            else:
                LOGGER.debug(
                    f"No existing tweets found in the database for user {self.username}"
                )
                self.get_users_tweets()
            # Write raw tweets to database
            self.db_conn.write_raw_tweets(self.tweets, self.author_id)
            # Clean the tweets
            clean_tweets = process_tweets(self.tweets)
            # Write clean tweets to DB
            self.db_conn.write_tweets(clean_tweets, self.author_id)


if __name__ == "__main__":
    TweetReader().get_tweets()