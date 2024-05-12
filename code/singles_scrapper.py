from bs4 import BeautifulSoup
import pandas as pd
import os 
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotipy.util as util
from tqdm.auto import tqdm
import argparse
import numpy as np
from dotenv import load_dotenv

def weighted_average_rating(avg_rating, num_votes, global_avg, smoothing_factor=10):
    """
    Calculates the weighted average rating based on the average rating, number of votes,
    global average rating, and a smoothing factor.
    
    Parameters:
    - avg_rating (float): The average rating of the item.
    - num_votes (int): The number of votes for the item.
    - global_avg (float): The global average rating.
    - smoothing_factor (int, optional): The smoothing factor to adjust the weight of the global average.
    
    Returns:
    - float: The weighted average rating.
    """
    t1 = ((avg_rating * num_votes) + (global_avg * smoothing_factor)) / (num_votes + smoothing_factor)
    return round(t1/10, 2)


def bayesian_average(avg_rating, num_votes, global_avg, prior_votes=50):
    """
    Calculates the Bayesian average rating based on the average rating, number of votes,
    global average rating, and prior votes.
    
    Parameters:
    - avg_rating (float): The average rating of the item.
    - num_votes (int): The number of votes for the item.
    - global_avg (float): The global average rating.
    - prior_votes (int, optional): The number of prior votes to consider. Default is 50.
    
    Returns:
    - float: The Bayesian average rating rounded to two decimal places.
    """
    t1 = ((avg_rating * num_votes) + (global_avg * prior_votes)) / (num_votes + prior_votes)
    return round(t1/10, 2)


def get_dataframe_from_soup(soup, min_nb_ratings, min_rating, min_weighted, base_url, headers, min_rating_tracks=80, min_votes_tracks=10, top_songs_keep=3):
    """
    Extracts information from the given BeautifulSoup object and returns a DataFrame.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object containing the HTML content.
        min_nb_ratings (int): The minimum number of user ratings required for an album to be included.
        min_rating (int): The minimum rating required for an album to be included.
        min_weighted (int): The minimum weighted average required for an album to be included.
        base_url (str): The base URL for album pages.
        headers (dict): The headers to be used for making HTTP requests.
        min_rating_tracks (int, optional): The minimum rating required for a track to be included. Defaults to 80.
        min_votes_tracks (int, optional): The minimum number of votes required for a track to be included. Defaults to 10.
        top_songs_keep (int, optional): The number of top-rated songs to keep for each album. Defaults to 3.

    Returns:
        pandas.DataFrame: A DataFrame containing the extracted information.
    """
    # Get DataFrame from the current page
    album_blocks = soup.find_all('div', class_='albumBlock five small')

    # Initialize lists to store extracted information
    dates = []
    artists = []
    albums = []
    ratings = []
    user_score_counts = []
    weighted_scores = []
    titles = []

    # Loop through each album block and extract the required information
    for album_block in album_blocks:
        
        
        len_votes = len(album_block.find('div', class_='ratingRowContainer').find_all('div', class_='rating'))
        # No votes
        if len_votes == 0:
            continue
        if album_block.find('div', class_='date') is None:
            continue
        date = album_block.find('div', class_='type').text
        artist = album_block.find('div', class_='artistTitle').text
        album_title = album_block.find('div', class_='albumTitle').text
        critic_score = album_block.find('div', class_='ratingRowContainer').find_all('div', class_='rating')[0].text
        
        # Both critic and user votes are present
        if len_votes == 2:
            user_score = album_block.find('div', class_='ratingRowContainer').find_all('div', class_='rating')[1].text
            user_score_count = int(album_block.find('div', class_='ratingRowContainer').find_all('div', class_='ratingText')[3].text.strip('()').replace(',', ''))
        # Only user votes is present
        elif len_votes == 1:
            user_score = album_block.find('div', class_='ratingRowContainer').find('div', class_='rating').text
            user_score_count = int(album_block.find('div', class_='ratingRowContainer').find_all('div', class_='ratingText')[1].text.strip('()').replace(',', ''))
        

        if int(user_score_count) >= min_nb_ratings and int(user_score) >= min_rating:
        
                
            weighted_score = weighted_average_rating(int(user_score), user_score_count, 74, smoothing_factor=15)


            # If it is an album: Get all the songs
            if base_url == 'https://www.albumoftheyear.org/releases/':
                # Extract the URL of the album
                album_url = album_block.find('a', href=True)['href']
                album_url = f"https://www.albumoftheyear.org{album_url}"
                
                # Get the HTML content of the album page
                response = requests.get(album_url, headers=headers) 
                soup = BeautifulSoup(response.content, 'html.parser')

                # Find all elements containing song ratings
                tracks = soup.find_all('tr')
                
                if len(tracks) == 0:
                    continue
                
                # Store track names and ratings in a dictionary
                track_ratings = {}
                for track in tracks:
                    if track.find('span') is None:
                        continue
                    name = track.find('a').text
                    rating = int(track.find('span').text)
                    votes = int(track.find('span')['title'].split()[0])
                    # Filtering tracks based on minimum rating and votes
                    if rating >= min_rating_tracks and votes >= min_votes_tracks:
                        track_ratings[name] = {'rating': rating, 'votes': votes}
                
                if len(track_ratings) == 0:
                    continue
                mean_rating = np.mean([rating['rating'] for name, rating in track_ratings.items()])
                
                if mean_rating < 82:
                    top_songs = sorted(track_ratings.items(), key=lambda x: x[1]['rating'], reverse=True)[:1]
                elif mean_rating < 84:
                    top_songs = sorted(track_ratings.items(), key=lambda x: x[1]['rating'], reverse=True)[:2]
                else:
                    # Find the top 3 best-rated songs
                    top_songs = sorted(track_ratings.items(), key=lambda x: x[1]['rating'], reverse=True)[:top_songs_keep]

                # Print the top 3 best-rated songs
                for name, rating in top_songs:
                    weighted_score = weighted_average_rating(rating['rating'], rating['votes'], 74, smoothing_factor=15)
                    # Append extracted information to lists
                    dates.append(date)
                    artists.append(artist)
                    titles.append(name)
                    albums.append(album_title)
                    ratings.append(rating['rating'])
                    user_score_counts.append(rating['votes'])
                    weighted_scores.append(weighted_score)
                        

            else:
                # Append extracted information to lists
                dates.append(date)
                artists.append(artist)
                titles.append(album_title)
                albums.append('Single')
                ratings.append(user_score)
                user_score_counts.append(user_score_count)
                weighted_scores.append(weighted_score)
        
    # Create a DataFrame from the extracted information    
    df = pd.DataFrame({
        'Date': dates,
        'Title': titles,
        'Artist': artists,
        'Album': albums,
        'Rating': ratings,
        'nb_votes': user_score_counts,
        'weighted':weighted_scores,
    })    
    # Convert to int
    df['Rating'] = df['Rating'].astype(int)  # Convert to float first, as there may be decimal values
    df['nb_votes'] = df['nb_votes'].astype(int)  # Remove commas and convert to int
    
    # Remove albums with weighted average below the minimum
    df = df[df['weighted'] >= min_weighted]
    
    return df


def scrape_multiple_pages(base_url, start_page, end_page, min_nb_ratings, min_rating, min_weighted):
    """
    Scrapes multiple pages of a website and returns a consolidated DataFrame.

    Parameters:
    - base_url (str): The base URL of the website.
    - start_page (int): The starting page number.
    - end_page (int): The ending page number.
    - min_nb_ratings (int): The minimum number of ratings required for a record to be included in the DataFrame.
    - min_rating (float): The minimum rating required for a record to be included in the DataFrame.

    Returns:
    - final_df (pandas.DataFrame): The consolidated DataFrame containing data from all the scraped pages.
    """

    # Initialize an empty DataFrame
    final_df = pd.DataFrame()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

    for page_num in tqdm(range(start_page, end_page + 1)):
            
        url = f'{base_url}{page_num}/'
        
        # Make a GET request with the User-Agent header
        try:
            response = requests.get(url, headers=headers, timeout=10)
        except Exception as e:
            print(f"Error: {e}")
            
        if response.status_code == 200:
            # Parse the HTML content with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get DataFrame from the current page
            df = get_dataframe_from_soup(soup, min_nb_ratings, min_rating, min_weighted, base_url, headers, min_rating_tracks=80, min_votes_tracks=7, top_songs_keep=3)

            # Append the current DataFrame to the final DataFrame
            final_df = pd.concat([final_df, df], ignore_index=True)
        else:
            print(f"Failed to fetch page {url}. Status code: {response.status_code}")

    print(f"Scraping complete. {final_df.shape[0]} records scraped.")
    return final_df



# =-----  Create a Spotify playlist ---------


def add_songs_to_playlist(singles_df, SPOTIPY_USERNAME, SPOTIPY_PLAYLIST_URI, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, cache_path):
    """
    Adds songs from a DataFrame to a Spotify playlist.

    Args:
        singles_df (pandas.DataFrame): DataFrame containing the songs to be added.
        username (str): Spotify username.
        playlist_uri (str): URI of the playlist to add the songs to.
        SPOTIPY_CLIENT_ID (str): Spotify API client ID.
        SPOTIPY_CLIENT_SECRET (str): Spotify API client secret.

    Returns:
        None
    """
    
    # Remove existing cached token

    # Set up Spotify API authentication
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(username=SPOTIPY_USERNAME, scope="playlist-modify-private",
                                                   client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, 
                                                   redirect_uri='http://localhost:8080', cache_path=cache_path))
 
    
    access_token = sp.auth_manager.get_cached_token()
    
    # Get the existing tracks in the playlist
    existing_tracks = get_all_playlist_tracks(sp, SPOTIPY_PLAYLIST_URI)
    
    # Extract track URIs
    existing_track_uris = set(track['track']['uri'] for track in existing_tracks)
    
    # Create a copy of the DataFrame
    singles_df_copy = singles_df.copy()
    
    # Iterate through the DataFrame and add new songs to the playlist
    for _, row in singles_df.iterrows():
        artist = row['Artist']
        track_name = row['Title']
        
         # Search for the track on Spotify
        results = sp.search(q=f"artist:{artist} track:{track_name}", type='track', limit=1)

        # Check if the search returned any results
        if results['tracks']['items']:
            track_uri = results['tracks']['items'][0]['uri']

            # Check if the track is not already in the playlist
            if track_uri not in existing_track_uris:
                # Add the track to the playlist
                sp.playlist_add_items(SPOTIPY_PLAYLIST_URI, [track_uri])
                print(f"Added '{artist} - {track_name}' to the playlist.")
                existing_track_uris.add(track_uri)
            else:
                # Remove the row from the DataFrame
                singles_df_copy.drop(index=row.name, inplace=True)
                # print(f"Skipping '{artist} - {track_name}' (already in the playlist).")
                
        else:
            # Remove the row from the DataFrame
            singles_df_copy.drop(index=row.name, inplace=True)
            print(f"Could not find '{artist} - {track_name}' on Spotify.")
            
    return singles_df_copy.iloc[::-1]

def delete_all_tracks_from_playlist(SPOTIPY_PLAYLIST_URI, SPOTIPY_USERNAME, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET):
    """
    Deletes all tracks from a given playlist.

    Parameters:
    - playlist_uri (str): The URI of the playlist to delete tracks from.
    - username (str): The username of the owner of the playlist.
    - SPOTIPY_CLIENT_ID (str): The client ID for the Spotify API.
    - SPOTIPY_CLIENT_SECRET (str): The client secret for the Spotify API.

    Returns:
    None
    """

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(username=SPOTIPY_USERNAME, scope="playlist-modify-private",
                                                   client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, 
                                                   redirect_uri='http://localhost:8080'))

    # Get the existing tracks in the playlist
    existing_tracks = get_all_playlist_tracks(sp, SPOTIPY_PLAYLIST_URI)

    # Extract track URIs
    track_uris = [track['track']['uri'] for track in existing_tracks]

    # Remove all tracks from the playlist
    sp.playlist_remove_all_occurrences_of_items(SPOTIPY_PLAYLIST_URI, track_uris)
    
    print(f"All tracks removed from the playlist {SPOTIPY_PLAYLIST_URI}.")


def get_all_playlist_tracks(sp, SPOTIPY_PLAYLIST_URI):
    """
    Fetches all tracks from a given Spotify playlist.

    Args:
        sp (spotipy.Spotify): An instance of the Spotipy client.
        SPOTIPY_PLAYLIST_URI (str): The URI of the Spotify playlist.

    Returns:
        list: A list of dictionaries representing the tracks in the playlist.
    """
    all_tracks = []
    
    # Initial request
    try:
        response = sp.playlist_tracks(SPOTIPY_PLAYLIST_URI, limit=50)
        all_tracks.extend(response['items'])

        # Continue fetching next pages
        while response['next']:
            response = sp.next(response)
            all_tracks.extend(response['items'])
            
        return all_tracks
    
    except spotipy.SpotifyException as e:
        if e.http_status == 404:
            print(f"Playlist not found: {SPOTIPY_PLAYLIST_URI}")
        else:
            print(f"Error: {e}")
            
        return []
    
    
def merge_albums_singles(singles_df, albums_df):
    """
    Merge the singles and albums dataframes and sort the resulting dataframe based on the 'Date' and 'weighted_avg' columns.

    Args:
        singles_df (pandas.DataFrame): DataFrame containing singles data.
        albums_df (pandas.DataFrame): DataFrame containing albums data.

    Returns:
        pandas.DataFrame: Merged and sorted DataFrame.

    """
    all_df = pd.concat([albums_df, singles_df], ignore_index=True)
    # Convert the 'Date' column to datetime, specifying the year as 2024
    all_df['time_stamp_date'] = pd.to_datetime(all_df['Date'] + ', 2024', format='%b %d, %Y')
    sorted_df = all_df.sort_values(by=['time_stamp_date', 'weighted'], ascending=[False, False])
    sorted_df = sorted_df.drop(columns=['time_stamp_date'])
    return sorted_df

def remove_already_added_tracks(sorted_df, SPOTIPY_USERNAME, SPOTIPY_PLAYLIST_URI, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET):
    """
    Removes already added tracks from a sorted DataFrame.

    Args:
        sorted_df (DataFrame): The sorted DataFrame containing the tracks.
        SPOTIPY_USERNAME (str): The Spotify username.
        SPOTIPY_PLAYLIST_URI (str): The URI of the Spotify playlist.
        SPOTIPY_CLIENT_ID (str): The Spotify client ID.
        SPOTIPY_CLIENT_SECRET (str): The Spotify client secret.

    Returns:
        DataFrame: A new DataFrame containing the tracks that are not yet in the playlist.
    """
    
    # Remove existing cached token
    util.prompt_for_user_token(SPOTIPY_USERNAME, scope="playlist-modify-private",
                            client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET,
                            redirect_uri='http://localhost:8080', cache_path=False)

    # Set up Spotify API authentication
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(username=SPOTIPY_USERNAME, scope="playlist-modify-private",
                                                    client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, 
                                                    redirect_uri='http://localhost:8080'))

    # Get the existing tracks in the playlist
    existing_tracks = get_all_playlist_tracks(sp, SPOTIPY_PLAYLIST_URI)

    # Get all songs in sorted_df that are not yet in the playlist (existing_tracks)
    new_songs = sorted_df[~sorted_df['Title'].isin([track['track']['name'] for track in existing_tracks])]
    return new_songs



# ------------------ Main ------------------
if __name__ == "__main__":
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(description='Scrape singles data and create a Spotify playlist.')
    parser.add_argument('--start_page', type=int, help='Starting page number for scraping (default: 1)', default=1)
    parser.add_argument('--end_page', type=int, help='Ending page number for scraping (default: 10)', default=10)
    parser.add_argument('--votes_album', type=int, help='Minimum number of ratings required (album) (default: 60)', default=60)
    parser.add_argument('--votes_single', type=int, help='Minimum number of ratings required (single) (default: 7)', default=7)
    parser.add_argument('--rating_album', type=int, help='Minimum rating required for the album (default: 74)', default=74)
    parser.add_argument('--rating_single', type=int, help='Minimum rating required for the singles (default: 76)', default=76)
    parser.add_argument('--weighted_single', type=float, help='Minimum weighted average required (single) (default: 7.77)', default=7.77)
    parser.add_argument('--weighted_album', type=float, help='Minimum weighted average required (album) (default: 7.6)', default=7.6)

    args = parser.parse_args()

    # Call the function to scrape multiple pages: Singles
    base_url = 'https://www.albumoftheyear.org/releases/singles/'
    
    print('1 ****** scrapping singles...')
    singles_df = scrape_multiple_pages(base_url, args.start_page, args.end_page, args.votes_single, args.rating_single, args.weighted_single)
    

    print('2 ****** scrapping albums...')
    base_url = 'https://www.albumoftheyear.org/releases/'
    albums_df = scrape_multiple_pages(base_url, args.start_page, args.end_page, args.votes_album, args.rating_album, args.weighted_album)
    
    # Merge albums and singles
    sorted_df = merge_albums_singles(singles_df, albums_df)
    
    print('3 ****** adding songs to spotify...')
    # Load environment variables from .env
    load_dotenv()

    # Get the cache path from the environment variable or use a default path
    cache_path = os.getenv('SPOTIPY_CACHE_PATH', '.cache-username')

    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
    SPOTIPY_USERNAME = os.getenv('SPOTIPY_USERNAME')
    SPOTIPY_PLAYLIST_URI = os.getenv('SPOTIPY_PLAYLIST_URI')
    
    # Remove already added tracks from the playlist
    new_songs = remove_already_added_tracks(sorted_df, SPOTIPY_USERNAME, SPOTIPY_PLAYLIST_URI, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET)
    # Add new songs to the playlist
    new_songs_spotify = add_songs_to_playlist(new_songs, SPOTIPY_USERNAME, SPOTIPY_PLAYLIST_URI, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, cache_path=cache_path)
    
    if new_songs_spotify.empty:        
        print('No new songs to add to the playlist.')
    else:
        print(new_songs_spotify.head(30))
