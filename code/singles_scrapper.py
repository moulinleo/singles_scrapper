from bs4 import BeautifulSoup
import pandas as pd
import os 
from tqdm import tqdm
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth


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


def get_dataframe_from_soup(soup, min_nb_ratings, min_rating, min_weighted):
    """
    Extracts information from the given BeautifulSoup object and returns a DataFrame.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object containing the HTML content.
        min_nb_ratings (int): The minimum number of user ratings required for an album to be included.
        min_rating (int): The minimum rating required for an album to be included.

    Returns:
        pandas.DataFrame: A DataFrame containing the extracted information.

    """
    album_blocks = soup.find_all('div', class_='albumBlock five small')

    # Initialize lists to store extracted information
    dates = []
    artists = []
    albums = []
    ratings = []
    user_score_counts = []

    # Loop through each album block and extract the required information
    for album_block in album_blocks:
        
        # Check if rating information is available
        rating_block = album_block.find('div', class_='ratingBlock')
        
        if rating_block:
        
            user_score_count = album_block.find('div', class_='ratingText', text='user score').find_next_sibling('div').text.strip().replace('(', '').replace(')', '').replace(',', '')
            
            if int(user_score_count) >= min_nb_ratings:
                
                rating = album_block.find('div', class_='rating').text.strip()

                if int(rating) >= min_rating:
                    date = album_block.find('div', class_='date').text.strip()
                    artist = album_block.find('div', class_='artistTitle').text.strip()
                    album = album_block.find('div', class_='albumTitle').text.strip()
                

                    # Append extracted information to lists
                    dates.append(date)
                    artists.append(artist)
                    albums.append(album)
                    ratings.append(rating)
                    user_score_counts.append(user_score_count)
                # Create a DataFrame
            
                
    df = pd.DataFrame({
        'Date': dates,
        'Artist': artists,
        'Album': albums,
        'Rating': ratings,
        'User_Vote_Count': user_score_counts
    })    
    
    df['Rating'] = df['Rating'].astype(int)  # Convert to float first, as there may be decimal values
    df['User_Vote_Count'] = df['User_Vote_Count'].astype(int)  # Remove commas and convert to int
    
    # Add weighted average
    # Weighted Average Rating
    df['weighted_avg'] = df.apply(lambda row: weighted_average_rating(row['Rating'], row['User_Vote_Count'], 74, smoothing_factor=15), axis=1)
    
    df = df[df['weighted_avg'] >= min_weighted]

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
        print(f"Fetching page {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
        except Exception as e:
            print(f"Error: {e}")
            
        if response.status_code == 200:
            # Parse the HTML content with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')

            # Get DataFrame from the current page
            df = get_dataframe_from_soup(soup, min_nb_ratings, min_rating, min_weighted)

            # Append the current DataFrame to the final DataFrame
            final_df = pd.concat([final_df, df], ignore_index=True)
            print(f"Page {page_num} scraped successfully.")
        else:
            print(f"Failed to fetch page {url}. Status code: {response.status_code}")

    print(f"Scraping complete. {final_df.shape[0]} records scraped.")
    return final_df



# =-----  Create a Spotify playlist ---------


def add_songs_to_playlist(singles_df, SPOTIPY_USERNAME, SPOTIPY_PLAYLIST_URI, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET):
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
    # Set up Spotify API authentication
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(username=SPOTIPY_USERNAME, scope="playlist-modify-private",
                                                   client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET, 
                                                   redirect_uri='http://localhost:8080'))

    
    # Get the existing tracks in the playlist
    existing_tracks = get_all_playlist_tracks(sp, SPOTIPY_PLAYLIST_URI)
    
    # Extract track URIs
    existing_track_uris = set(track['track']['uri'] for track in existing_tracks)
    
    # Iterate through the DataFrame and add new songs to the playlist
    for _, row in singles_df.iterrows():
        artist = row['Artist']
        track_name = row['Album']
        
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
                pass
                
        else:
            print(f"Could not find '{artist} - {track_name}' on Spotify.")
            

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
    
    print(f"Playlist URI: {SPOTIPY_PLAYLIST_URI}")

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

    

# Specify the range of pages you want to scrape
start_page = 1
end_page = 20  # Adjust this based on the total number of pages you want to scrape

min_nb_ratings = 7
min_rating = 76
min_weighted = 7.5

# Call the function to scrape multiple page: Singles
base_url = 'https://www.albumoftheyear.org/releases/singles/'


print('1 ****** scrapping singles...')
singles_df = scrape_multiple_pages(base_url,start_page, end_page, min_nb_ratings, min_rating, min_weighted)

print('2 ****** loading env variables...')
# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_USERNAME = os.getenv('SPOTIPY_USERNAME')
SPOTIPY_PLAYLIST_URI = os.getenv('SPOTIPY_PLAYLIST_URI')

add_songs_to_playlist(singles_df, SPOTIPY_USERNAME, SPOTIPY_PLAYLIST_URI, SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET)

print(singles_df.head(30))