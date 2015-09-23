import numpy as np
import pandas as pd
import create_model as cm

class Leaderboards(object):
    def __init__(self, speeds):
        '''
        Input:  Dataframe of segment_id, athlete_id, average speed, and seg_average_grade
        '''
        self.speeds = speeds

    def store(self, board_type, ratings_df, board_size=20):
        '''
        Input:  DataFrame of ratings, size of leaderboards
        Output: None
        
        Store each of the leaderboards from the leaderboard list from get in app_data folder as csvs
        '''
        leaderboards = self.get(board_type, ratings_df, board_size)
        for key in leaderboards.keys():
            leaderboards[key].to_csv('../app/app_data/{}_{}_leaderboard.csv'.format(board_type, key))

    def get(self, board_type, ratings_df, board_size=20):
        '''
        Input:  DataFrame of ratings, size of leaderboards
        Output: List of DataFrames with the top n_leaders ratings and their rank 
                for each latent feature
        '''
        # Store the Dataframe of ratings and requested leaderboard size
        self.board_type = board_type
        self.board_direction = -1 if board_type == 'athlete' else 1
        self.ratings = ratings_df
        self.board_size = -1 if board_size == 'all' else board_size

        # Make scaled ratings df
        self.scaled_ratings = ratings_df.copy(deep=True)
        for column in self.ratings.columns:
            self.scale_column_ratings(column)

        # Make leaderboard dict
        leaderboards = {column: self.get_n_leaders(column) for column in self.ratings.columns}

        return leaderboards

    def get_n_leaders(self, rating_column):
        '''
        Input:  Column from user latent feature (rating) matrix
        Output: DataFrame of top n leaders and their ratings for input column
        '''
        # Get the indicies of the sorted scaled ratings
        good_ratings = self.scaled_ratings[rating_column].dropna()
        sorted_scaled_ratings_indices = np.argsort(good_ratings.values)

        # We only want the top n leaders for the leaderboard
        top_n_indices = sorted_scaled_ratings_indices[-1:-self.board_size-1:-1]
        
        # Grab the top n leaders and their rating_column stats
        n_leaders = good_ratings.iloc[top_n_indices]
        n_leaders_df = n_leaders.reset_index()
        
        # Get those leaders average speeds
        group = '{}_id'.format(self.board_type)
        avg_speeds = self.speeds.groupby(group).average_speed.mean().reset_index()

        # Join average speeds with leaderboard
        n_leaders_df = pd.merge(n_leaders_df, avg_speeds, on=group, how='left')

        # Make new column, rank, ranging from 1 - n
        worst_rank = n_leaders_df.shape[0] if self.board_size == -1 else self.board_size
        n_leaders_df['rank'] = range(1, worst_rank+1)

        # Set it to be the index
        n_leaders_df.set_index('rank', inplace=True)

        return n_leaders_df

    def scale_column_ratings(self, rating_column):
        '''
        Input:  DataFrame of latent features (ratings)
        Output: Copy of ratings 

        Scales ratings from current to 0 - 100, by column
        '''
        # Athletes in column
        athletes = self.scaled_ratings[pd.notnull(self.scaled_ratings[rating_column])].index

        # Make np array of those athletes columns ratings
        scaled_ratings_column = self.scaled_ratings.ix[athletes][rating_column]
    
        # Figure out the orentation of ratings scale
        orientation = self.get_orientation(scaled_ratings_column, rating_column)

        # Make sure that the ratings are correctly oriented
        scaled_ratings_column *= self.board_direction * orientation

        # Add the magnitude of the minimum rating to all, columnwise
        scaled_ratings_column -= scaled_ratings_column.min()

        # Multiply by the ratio of 100:(new max rating), columnwise
        scaled_ratings_column *= 100. / scaled_ratings_column.max() 

        # Set the newly scaled column values back into the scaled df
        self.scaled_ratings[rating_column] = scaled_ratings_column.dropna()

    def get_orientation(self, scaled_ratings_column, rating_column):
        '''
        Input: Ratings column pandas series, name of column to check orientation
        Output: 1 or -1 depending on how a rating scale is oriented
        '''
        # Get correct name from rating_column to index into subset_querys_dict with
        dict_name = rating_column[:-7]

        # Get corresponding query
        subset_query = cm.subset_querys_dict[dict_name]

        # Subset scaled_ratings_column
        avg_speed_subset = self.speeds.query(subset_query) if subset_query else self.speeds

        # Group avg_speed_subset by board_type
        type_mean_speed = avg_speed_subset.groupby('{}_id'.format(self.board_type)) \
                                                  .average_speed.mean()

        # "Best" board_type by rating in scaled_ratings_column
        best = scaled_ratings_column.idxmax()

        return -1 if type_mean_speed.ix[best] > type_mean_speed.mean() else 1

