import json
import numpy as np
import pandas as pd
from pymongo import MongoClient

class EffortDfGetter(object):
    '''
    Class for retrieving a DataFrame with Strava efforts from either raw json file or mongo database
    '''
    def __init__(self, origin='json'):
        '''
        Input: String specifiying where the original data is coming from
        '''
        self.origin = origin

    def get(self, size=False):
        '''
        Input: Size if origin is mongo
        Output: Clean DataFrame of Strava efforts
        '''
        self.df = self.get_df_from_json() if self.origin == 'json' else self.get_df_from_mongo(size)
        self.transform_df()
        return self.df

    def transform_df(self):
        '''
        Helper function that calls all necessary functions to change DataFrame into proper type
        '''
        self.make_id_cols()
        self.get_segment_info()
        self.make_date_col()
        self.engineer_features()
        self.remove_useless_rows()
        self.remove_useless_columns()
        #self.remove_outliers()

    def get_df_from_json(self):
        '''
        Function to get data from raw json file
        Output: DataFrame from raw json file
        '''
        with open('../data/efforts.json') as f:
            return pd.DataFrame(json.loads(line) for line in f)

    def get_df_from_mongo(self, size=False):
        '''
        Function to get data from raw json file
        Input: Size of dataframe to be retrieved
        Output: DataFrame from mongo database
        '''
        client = MongoClient()
        db = client['Strava']
        table = db['segment_efforts']
        if size:
            df = pd.DataFrame(list(table.find().limit(size)))
        else:
            df = pd.DataFrame(list(table.find()))
        return df

    def make_id_cols(self):
        '''
        Function to parse ids from nested dictionaries
        '''
        # Specify which column names have desired ids
        columns = ['athlete', 'segment', 'activity']

        # Make a new column in the df from each of the ids
        for column in columns:
            self.df['{}_id'.format(column)] = self.df[column].apply(lambda x: x['id'])

    def get_segment_info(self):
        '''
        Function to get the information stored in the nested dictionary about the segment
        '''
        # Specify which elements of the segment dictionary to keep
        categories = ['average_grade', 'distance', 'elevation_low', 
                      'elevation_high', 'maximum_grade']

        # Make a new column in the df for each of the segment elements
        for category in categories:
            self.df['seg_{}'.format(category)] = self.df.segment.apply(lambda x: x[category])

    def make_date_col(self):
        '''
        Function to make datetime column out of date column
        '''
        self.df['date'] = pd.to_datetime(self.df.start_date_local)

    def engineer_features(self):
        '''
        Function to engineer features from now existing columns
        '''
        # Dummies for whether or not the effort had cadence or heartrate tracking for the effort
        self.df['tracks_cadence'] = ~pd.isnull(self.df.average_cadence)
        self.df['tracks_heartrate'] = ~pd.isnull(self.df.average_heartrate)

        # Difference between the specified segment distance and the effort's recorded ride distance
        self.df.eval('dist_diff = seg_distance - distance')

        # Speed = Distance / Time
        self.df.eval('average_speed = distance / elapsed_time')

    def remove_useless_rows(self):
        '''
        Function to get rid of efforts that have no useful information
        '''
        # Only keep efforts with a positive recorded moving time
        self.df = self.df.query('moving_time > 0')

    def remove_useless_columns(self):
        '''
        Function to get rid of columns that are no longer useful
        '''
        # List of useless columns
        columns = ['max_heartrate', 'resource_state', 'name', 'kom_rank', 'start_index', 'pr_rank',
                   'id', '_id', 'achievements', 'end_index', 'segment', 'athlete', 'start_date', 
                   'start_date_local', 'average_cadence', 'average_heartrate', 'activity']
        
        # Drop all the useless columns
        self.df.drop(columns, inplace=True, axis=1)

    def remove_outliers(self):
        '''
        Function to remove athlete effort outliers, as measured by their naively calculated expected
        speed.
        '''
        # Averge speed per athlete
        athlete_average_speed = self.df.groupby('athlete_id').average_speed.mean()

        # Average speed and standard deviation per segment
        segment_average_speed = self.df.groupby('segment_id').average_speed.mean()
        segment_speed_std = self.df.groupby('segment_id').average_speed.std()

        df = pd.merge(self.df, athlete_average_speed, left_on='athlete_id', 
                      right_index=True, suffix=('', '_overall'))

    def remove_outliers_old(self):
        '''
        Function to remove 6 signma outliers for average speed on a segment-wise basis

        Concatenated together all of the efforts that have average speeds within 3 sigma of the
        mean speed for their respective segments
        '''
        # Get list of segment-athlete pairs
        segments = list(self.df.segment_id.unique())

        # Get list of inlier dfs 
        inlier_efforts = [self.get_inliers(segment) for segment in segments]
        self.df = pd.concat(inlier_efforts, ignore_index=True)

    def get_inliers(self, segment):
        '''
        Function to remove 6 sigma outliers for average speed for a given segment-athlete pair
        Input:  Segment ID
        '''
        # Just the efforts for the specified segment-athlete pair from the full df
        segment_athlete_subset = self.df.query('segment_id == @segment')

        # Calculate the mean and standard deviation for average_speed for that segment-athlete pair
        sp_mean = segment_athlete_subset.average_speed.mean()
        sp_std = segment_athlete_subset.average_speed.std()

        # Query string for getting efforts that have speeds within 3 sigma of the mean
        inlier_query = '@sp_mean - 3 * @sp_std < average_speed < @sp_mean + 3 * @sp_std'

        # Return only those efforts within the speed requirements
        segment_athlete_inliers = segment_athlete_subset if np.isnan(sp_std) else \
                                  segment_athlete_subset.query(inlier_query)
        return segment_athlete_inliers

    def remove_outliers(group):
        '''
        Possible pandas groupby transform solution:
        df.groupby(['segment_id', 'athlete_id']).tranform(remove_outliers)

        Note: might be faster if somehow the function on the groupby object retured the indicies
              of the efforts that are "outliers" so they can all be removed at once.
        '''
        mean, std = group.mean(), group.std()
        outliers = (group - mean).abs() > 3 * std
        inliers = group[~outliers]
        return inliers
