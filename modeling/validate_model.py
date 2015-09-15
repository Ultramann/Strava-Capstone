import random
import numpy as np
import pandas as pd
import graphlab as gl
import create_model as cm

def plot_ratings(ratings_df):
    '''
    Input: DataFrame of decomposed ratings
    Output: None

    Plots histogram of the ratings in ratings_df and a sample from the frame
    '''
    # Get scale for binning in hist depending on what df we're plotting for
    bins_scale = 5 if ratings_df.index.name == 'segment_id' else 300

    # Plot hist with scaled number of bins
    ratings_df.hist(bins=ratings_df.shape[0]/bins_scale, figsize=(10, 5))

    # Plot random sample of ratings
    sample_ratings = ratings_df.ix[random.sample(ratings_df.index, 50)]
    sample_ratings.plot(kind='bar', stacked='True', figsize=(20, 10))

def evaluate_latent_feature_correlations(df, segment_ratings):
    '''
    Input: Training DataFrame, DataFrame of segment ratings
    Output: Correlation matrix for the ratings from segment_ratings
    '''
    # Get list of rating column names
    rating_columns = list(segment_ratings.columns.values) 

    # Make list of all columns to grab from full dataframe
    segment_columns = ['seg_average_grade', 'seg_distance', 'seg_maximum_grade'] + rating_columns
                       
    # Get one instance of all info for each segment
    segment_df = df.groupby('segment_id').first()

    # Join segment info with the latent feature ratings for each segment
    segment_correlation = segment_df.merge(segment_ratings, 
                                           right_index=True, 
                                           left_index=True)[segment_columns].corr()

    # Return just the rating columns from the correlation df
    return segment_correlation[rating_columns]

def split_efforts(df, date='2015-08-01'):
    '''
    Input:  Full effort DataFrame
    Output: Training effort DF, Testing effort DF

    Subsets full effort df into training df, consistant of efforts before "date" and testing df of
    efforts after date for athletes with efforts before date.
    '''
    # Split into training and testing sets on "date"
    training_df = df.query('date <= @date')
    testing_df = df.query('date > @date')

    # Get list of unique athletes in both subsets
    athletes_in_train = training_df.athlete_id.unique()
    athletes_in_test = testing_df.athlete_id.unique()

    # Only use athletes who have efforts both before and after date
    athletes_to_use = set(athletes_in_train).intersection(set(athletes_in_test))

    # Modify test df to reflect that subset of athletes
    testing_df = testing_df.query('athlete_id in @athletes_to_use')

    return training_df, testing_df

def testing_rmse(models, testing_df):
    '''
    Input: Dictionary of trained GraphLab recommender models, Test observation DataFrame
    Output: Dictionary of RMSEs for testing_df and subsets

    Get the root mean squared error for the test data's predicted values from the models for the
    total testing df and the respective subsets.
    '''
    # Get all subset dfs from testing df
    dfs_for_test = cm.get_dfs_for_model(testing_df, models.keys())

    # Get all subset sfs from testing df
    sfs_for_test = cm.get_sfs_for_model(testing_df, models.keys())

    # Predict on testing data SFrame with model
    predictions = {name: np.array(models[name].predict(sf)) for name, sf in 
                   sfs_for_test.items()}

    # Calculate root mean squared error between actual test data and predicted values from model
    def rmse(df, prediction):
        agg_df = df.groupby(['athlete_id', 'segment_id']).mean().average_speed
        return (((agg_df.values - prediction) ** 2) ** 0.5).mean()

    rmses = {name: rmse(df, predictions[name]) for name, df in dfs_for_test.items()}
    return rmses
