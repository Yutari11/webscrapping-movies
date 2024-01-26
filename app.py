from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
import numpy as np
import time
import selenium
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select
import streamlit as st

adresse_set_up = False

st.set_page_config(
    page_title="Projet 2 NLP ",
    page_icon="💻",
)

st.title("Projet Webscraping - Movies and screenings")
app_en_cour = st.sidebar.radio("Page selector",['Main page',"UGC",'CGR','Pathé','MK2'])

cinemasFrance = pd.read_excel("DonnéesCartographie2022Cinemas.xlsx")
cinemasFrance["code INSEE"] = cinemasFrance["code INSEE"].apply(lambda x: x[:2] + "0" + x[3:] if x[:2] == "75" else x)
cinemasFrance = cinemasFrance[(cinemasFrance["programmateur"] == "CGR") |
              (cinemasFrance["programmateur"] == "UGC") |
              (cinemasFrance["programmateur"] == "MK2") |
              (cinemasFrance["programmateur"] == "PATHE-GAUMONT")]

url_mk2 = pd.DataFrame(columns=['nom', 'url'])

rows = [
    ['MK2 BEAUBOURG', "https://www.mk2.com/salle/mk2-beaubourg"],
    ['MK2 ODEON COTE SAINT-MICHEL', "https://www.mk2.com/salle/mk2-odeon-st-germain-st-michel"],
    ['MK2 ODEON COTE SAINT-GERMAIN', "https://www.mk2.com/salle/mk2-odeon-st-germain-st-michel"],
    ['MK2 PARNASSE', "https://www.mk2.com/salle/mk2-parnasse"],
    ['MK2 QUAI DE SEINE', "https://www.mk2.com/salle/mk2-quai-seine-quai-loire"],
    ['MK2 GAMBETTA', "https://www.mk2.com/salle/mk2-gambetta"],
    ['MK2 BASTILLE COTE FAUBOURG SAINT-ANTOINE', "https://www.mk2.com/salle/mk2-bastille-beaumarchais-fg-st-antoine"],
    ['MK2 BASTILLE COTE BEAUMARCHAIS', "https://www.mk2.com/salle/mk2-bastille-beaumarchais-fg-st-antoine"],
    ['MK2 NATION', "https://www.mk2.com/salle/mk2-nation"],
    ['MK2 BIBLIOTHEQUE', "https://www.mk2.com/salle/mk2-bibliotheque"],
    ['MK2 A&E', "https://www.mk2.com/salle/mk2-bibliotheque"],
    ['MK2 QUAI DE LOIRE', "https://www.mk2.com/salle/mk2-quai-seine-quai-loire"]

]
for i, row in enumerate(rows):
    url_mk2.loc[i] = row


def get_letterboxd_info(driver, movie):
    #We set the current URL of the driver to the Letterboxd main page
    url_letterboxd = "https://letterboxd.com/"
    driver.get(url_letterboxd)
    
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    driver.implicitly_wait(1)
    time.sleep(3)
    
    #We need to discard the pop-ups of the cookies on the page
    pop_up = driver.find_elements(By.CLASS_NAME, 'fc-cta-do-not-consent')
    if pop_up:
        pop_up[0].click()

    #Now, we search for the movie in question
    search_bar = driver.find_element(By.ID, 'search-q')
    search_bar.clear()
    search_bar.send_keys(movie)
    search_bar.send_keys(Keys.RETURN)
    link_element = driver.find_element(By.XPATH, '//a[text()="Films"]')
    link_element.click()

    #We click on the first movie in the list
    results = driver.find_elements(By.CLASS_NAME, "results")
    if not results:
        return {}
    movies_details = results[0].find_elements(By.CLASS_NAME, "film-detail-content")
    header = movies_details[0].find_element(By.CLASS_NAME, "headline-2")
    movie_link = header.find_element(By.TAG_NAME, "a")
    movie_link.click()

    #Now we need to get the info on the movie: the director's name, the ratings and the genre
    #We scroll down the page to avoid the ads.
    time.sleep(1)
    footer = driver.find_element(By.TAG_NAME, "footer")
    delta_y = footer.rect['y']
    ActionChains(driver)\
        .scroll_by_amount(0, 500)\
        .perform()

    driver.find_element(By.XPATH, '//*[@id="crew"]').click()
    directors = driver.find_elements(By.XPATH, '//*[@id="tab-crew"]/div[1]/p/a')
    directors = list(map(lambda x: x.text, directors))

    ratings = driver.find_elements(By.CLASS_NAME, "average-rating")
    if ratings:
        rating = ratings[0].find_element(By.TAG_NAME, "a").text
    else:
        rating = np.nan
    
    driver.find_element(By.XPATH, '//*[@id="tabbed-content"]/header/ul/li[4]/a').click()
    genres = driver.find_elements(By.ID, "tab-genres")
    if genres:
        genres = genres[0].find_elements(By.TAG_NAME, "a")
        genres = list(map(lambda x: x.text, genres))
    else:
        genres = []
    return {'ratings': rating, 'genres': genres, 'directors': directors}

def update_list_of_screenings(driver, list):
    for i in range(len(list)):
        info = get_letterboxd_info(driver, list[i]['title'])
        list[i].update(info)
    return list

def main_page():
    global cinemasProches, cinemasProchesCGR, cinemasProchesMK2, cinemasProchesUGC, cinemasProchesPathe
    st.title("Main Page")
    adresse= st.text_input("Quelle est votre adresse ?", key="question_input")
    slider = st.slider(
        "Choisissez le périmètre dans lequel selectionner les cinémas proches de vous : ",
        min_value = 1,
        max_value = 50,
        value = 10,
        step = 1
    )
    if st.button("Entrer"):
        if adresse:
            adresse_set_up = True
            loc = Nominatim(user_agent="Geopy Library")
            getLoc = loc.geocode(adresse)
            st.write(f"Votre adresse est : {getLoc.address}")
            st.write(f"Latitude : {getLoc.latitude}")
            st.write(f"Longitude : {getLoc.longitude}")
            
            dist_max_km = slider
            coord_user = (getLoc.latitude, getLoc.longitude)

            cinemasCloseBool = cinemasFrance.apply(
                lambda x: geodesic(
                    coord_user,
                    (x["latitude"], x["longitude"])
                    ).km < dist_max_km,
                axis = 1
                )
            
            cinemasProches = cinemasFrance[cinemasCloseBool]
            cinemasProchesUGC = cinemasProches[cinemasProches["programmateur"] == "UGC"]
            cinemasProchesCGR = cinemasProches[cinemasProches["programmateur"] == "CGR"]
            cinemasProchesPathe = cinemasProches[cinemasProches["programmateur"] == "PATHE-GAUMONT"]
            cinemasProchesMK2 = cinemasProches[cinemasProches["programmateur"] == "MK2"]
            st.session_state.cinemasProches = cinemasProches
            st.session_state.cinemasProchesUGC = cinemasProchesUGC
            st.session_state.cinemasProchesCGR = cinemasProchesCGR
            st.session_state.cinemasProchesPathe = cinemasProchesPathe
            st.session_state.cinemasProchesMK2 = cinemasProchesMK2


        st.dataframe(cinemasProches)

def find_UGC_cinema(driver, theater_name):
    #We set the current URL of the driver to the search page for UCG movie theaters
    url_ugc = "https://www.ugc.fr/cinemas.html"
    driver.get(url_ugc)
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    time.sleep(1)

    #We use the search bar to search for a specific theater, which name is contained in the previous dataframes
    search_bar = driver.find_element(By.ID, 'search-cinemas-field')
    search_bar.clear()
    driver.implicitly_wait(1)
    search_bar.send_keys(theater_name)
    driver.implicitly_wait(1)
    
    #We search for the list of theaters displayed
    cinema_list = driver.find_element(By.ID, "nav-cinemas")
    
    #We then find the list of all theaters. The UGC website is engineered in a way that all theaters are still loaded after the query, but
    #only those that match the query are displayed. The others are simply hidden by modifying the style attribute.
    cinema_list_items = cinema_list.find_elements(By.CLASS_NAME, 'component--cinema-list-item')
    visible_elements = [element for element in cinema_list_items if element.get_attribute('style') == ""]
    #Now that we have the list of movie theaters, there should only be one item in the list. Either way, we take the first one, and take its website link
    #There we will be able to find all the movies that have screenings.
    if visible_elements:
        first_cinema = visible_elements[0]
        first_link = first_cinema.find_element(By.TAG_NAME, 'a')
        href_value = first_link.get_attribute('href')
        print(href_value)
        return href_value
    else:
        print("Aucun cinéma")
        return("")

def get_movies_UGC(driver, theaterpage):
    #We set the current URL of the driver to the wanted UGC theater
    driver.get(theaterpage)
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    time.sleep(5)
    pop_ups = driver.find_elements(By.ID, 'didomi-notice-disagree-button')
    if pop_ups:
        pop_ups[0].click()
    time.sleep(2)
    driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
    #We search for the container for all movies in the page
    movie_container = driver.find_element(By.CLASS_NAME, "dates-content")
    
    #Next, we get the list of all the containers of movie info
    list_of_movies = movie_container.find_elements(By.CLASS_NAME, 'slider-item')
    #Now that we have the list of movies, we will go in each one of them, and access their title (only their title for now)
    if list_of_movies:
        list_of_movies_screenings = []
        for movie in list_of_movies:
            if (len(movie.find_elements(By.CLASS_NAME, 'component--screening-cards')) == 0):
                continue
            if (movie.find_elements(By.CLASS_NAME, 'film-tag')) and (movie.find_elements(By.CLASS_NAME, 'film-tag')[0].text in [" Opéra ", " Ballet "]):
                print("DAS NOT A FILM")
                continue
                
            movie_info = movie.find_element(By.CLASS_NAME, 'block--title')
            movie_title = movie_info.find_element(By.CSS_SELECTOR, "a[data-film-label]")
            title = movie_title.text
            print(title)
    
            screenings = []
            screenings_list = driver.find_element(By.CLASS_NAME, 'component--screening-cards')
            screenings_list = screenings_list.find_elements(By.TAG_NAME, 'button')
    
            for s in screenings_list:
                lang = s.find_element(By.TAG_NAME, 'span').text
                start = s.find_element(By.CLASS_NAME, 'screening-start').text
                end = s.find_element(By.CLASS_NAME, 'screening-end').text
                room = s.find_element(By.CLASS_NAME, 'screening-detail').text
                screenings.append({'lang': lang, 'start': start, 'end': end, 'room': room})
    
            list_of_movies_screenings.append({'title': title, 'screenings': screenings})
        return list_of_movies_screenings
    else:
        print("Pas de film pour aujourd'hui")
        return([])

def UGC():
    st.write("Voici les cinémas UGC proches de chez vous, selon l'adresse renseignée en page d'accueil :")
    cinemasProchesUGC = st.session_state.cinemasProchesUGC
    st.dataframe(cinemasProchesUGC)
    liste_ugc = list(cinemasProchesUGC.apply(lambda x: x["nom"] + ", " + x["adresse"] + ", " + x["commune"], axis = 1))
    cinema_choisi = st.selectbox("Choisissez le cinéma que vous voulez :", liste_ugc)
    if st.button("Lancer la recherche"):
        driver = webdriver.Chrome()
        driver.set_window_size(1920,1080)
        cinema_choisi_url = find_UGC_cinema(driver, "".join([i for i in cinema_choisi.split(',')[1] if not i.isdigit()])[1:] )
        films = get_movies_UGC(driver, cinema_choisi_url)
        films_updated = update_list_of_screenings(driver, films)
        films_ugc = pd.DataFrame(films_updated).sort_values(by = "ratings", ascending= False)
        driver.quit()
        st.dataframe(films_ugc)


def find_CGR_cinema(driver, theater_name):
    #We set the current URL of the driver to the search page for UCG movie theaters
    url_ugc = "https://www.cgrcinemas.fr/cinema/"
    driver.get(url_ugc)
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    time.sleep(1)

    #We use the search bar to search for a specific theater, which name is contained in the previous dataframes
    pop_up = driver.find_elements(By.ID, "didomi-notice-disagree-button")
    if pop_up:
        pop_up[0].click()
    
    search_bar = driver.find_element(By.CLASS_NAME, 'css-4bl6n9')
    search_bar.clear()
    driver.implicitly_wait(1)
    search_bar.send_keys(theater_name)
    driver.implicitly_wait(1)
    
    #We search for the list of theaters displayed
    cinema_list = driver.find_element(By.XPATH, "/html/body/div[2]/div[1]/div/div[1]/div[3]/div/div/div/div[3]/div/div")
    
    #We then find the list of all theaters. The UGC website is engineered in a way that all theaters are still loaded after the query, but
    #only those that match the query are displayed. The others are simply hidden by modifying the style attribute.
    cinema_list_items = cinema_list.find_elements(By.CLASS_NAME, 'css-fd6b40')
    #Now that we have the list of movie theaters, there should only be one item in the list. Either way, we take the first one, and take its website link
    #There we will be able to find all the movies that have screenings.
    if cinema_list_items:
        first_cinema = cinema_list_items[0]
        first_link = first_cinema.find_element(By.CLASS_NAME, 'css-xe0135')
        href_value = first_link.get_attribute('href')
        print(href_value)
        return href_value
    else:
        print("Aucun cinéma")
        return("")

def get_movies_CGR(driver, theaterpage):
    #We set the current URL of the driver to the wanted UGC theater
    driver.get(theaterpage)
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    time.sleep(5)
    pop_ups = driver.find_elements(By.ID, 'didomi-notice-disagree-button')
    if pop_ups:
        pop_ups[0].click()
        
    #We search for the container for all movies in the page
    movie_container = driver.find_element(By.CLASS_NAME, "css-1axjb46")
    films_a_l_affiche = []
    
    #Next, we get the list of all the containers of movie info
    list_of_movies = movie_container.find_elements(By.CLASS_NAME, 'css-1acoij0')
    
    #Now that we have the list of movies, we will go in each one of them, and access their title (only their title for now)
    if list_of_movies:
        for movie in list_of_movies:
            movie_title = movie.find_element(By.CLASS_NAME, "css-efkg2u")
            title = movie_title.text
            print(title)
            films_a_l_affiche.append({'title': title})

    
    #Now, we do this all over again for the next container of movies on the page
    movie_container = driver.find_element(By.CLASS_NAME, "css-eqwlce")
    list_of_movies = movie_container.find_elements(By.CLASS_NAME, 'css-1acoij0')
    
    #Now that we have the list of movies, we will go in each one of them, and access their title (only their title for now)
    if list_of_movies:
        for movie in list_of_movies:
            movie_title = movie.find_element(By.CLASS_NAME, "css-efkg2u")
            title = movie_title.text
            print(title)
            films_a_l_affiche.append({'title': title})
    
    if films_a_l_affiche:
        return films_a_l_affiche
        
    else:
        print("Pas de film à l'affiche")
        return([])


def CGR():
    st.write("Voici les cinémas CGR proches de chez vous, selon l'adresse renseignée en page d'accueil :")
    cinemasProchesUGC = st.session_state.cinemasProchesCGR
    st.dataframe(cinemasProchesCGR)
    liste_cgr = list(cinemasProchesCGR.apply(lambda x: x["nom"] + ", " + x["adresse"] + ", " + x["commune"], axis = 1))
    cinema_choisi = st.selectbox("Choisissez le cinéma que vous voulez :", liste_cgr)
    if st.button("Lancer la recherche"):
        driver = webdriver.Chrome()
        driver.set_window_size(1920,1080)
        cinema_choisi_url = find_CGR_cinema(driver, "".join([i for i in cinema_choisi.split(',')[1] if not i.isdigit()])[1:] )
        films = get_movies_CGR(driver, cinema_choisi_url)
        films_updated = update_list_of_screenings(driver, films)
        films_cgr = pd.DataFrame(films_updated).sort_values(by = "ratings", ascending= False)
        driver.quit()
        st.dataframe(films_cgr)

def find_mk2_cinema(nom):
    result = url_mk2[url_mk2["nom"] == nom]["url"]
    return result[0] if result.any() else None

def get_movies_mk2(driver, theaterpage):
    #We set the current URL of the driver to the wanted UGC theater
    driver.get(theaterpage)
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    time.sleep(1)
    pop_ups = driver.find_elements(By.ID, 'CybotCookiebotDialogBodyButtonDecline')
    if pop_ups:
        pop_ups[0].click()
    time.sleep(2)
    select_element = driver.find_elements(By.ID, "cinema-group-picker")
    if select_element:
        select = Select(select_element[0])
        select.select_by_index(1)
        time.sleep(2)
        valider_button = driver.find_element(By.XPATH, "/html/body/div[2]/div/div[2]/div/div/form/button")
        valider_button.click()

    #Next, we get the list of all the containers of movie info
    list_of_movies_selector = driver.find_element(By.XPATH, '/html/body/div[1]/div[1]/main/section[2]/div[2]/section')
    list_of_movies = list_of_movies_selector.find_elements(By.TAG_NAME, 'section')
    
    #Now that we have the list of movies, we will go in each one of them, and access their title (only their title for now)
    if list_of_movies:
        films_a_l_affiche = []
        for movie in list_of_movies:
            movie_title = movie.find_element(By.TAG_NAME, "h4")
            title = movie_title.text
            print(title)
            screenings = []
            screenings_list = movie.find_element(By.TAG_NAME, 'ol')
            screenings_list = screenings_list.find_elements(By.TAG_NAME, "li")
            for s in screenings_list:
                lang = s.find_element(By.TAG_NAME, 'h6').text
                start = s.find_element(By.TAG_NAME, 'h5').text
                screenings.append({'lang': lang, 'start': start})
    
            films_a_l_affiche.append({'title': title, 'screenings': screenings})
    
    if films_a_l_affiche:
        return films_a_l_affiche
        
    else:
        print("Pas de film à l'affiche")
        return([])

def MK2():
    st.write("Voici les cinémas MK2 proches de chez vous, selon l'adresse renseignée en page d'accueil :")
    cinemasProchesMK2 = st.session_state.cinemasProchesMK2
    st.dataframe(cinemasProchesMK2)
    liste_mk2 = list(cinemasProchesMK2.apply(lambda x: x["nom"] + ", " + x["adresse"] + ", " + x["commune"], axis = 1))
    cinema_choisi = st.selectbox("Choisissez le cinéma que vous voulez :", liste_mk2)
    if st.button("Lancer la recherche"):
        driver = webdriver.Chrome()
        driver.set_window_size(1920,1080)
        cinema_choisi_url = find_CGR_cinema(driver, "".join([i for i in cinema_choisi.split(',')[1] if not i.isdigit()])[1:] )
        films = get_movies_mk2(driver, cinema_choisi_url)
        films_updated = update_list_of_screenings(driver, films)
        films_mk2 = pd.DataFrame(films_updated).sort_values(by = "ratings", ascending= False)
        driver.quit()
        st.dataframe(films_mk2)


def get_movies_pathe(driver, theaterpage):
    #We set the current URL of the driver to the wanted UGC theater
    #driver.get(theaterpage)
    #We need to let the browser load everything, so we buffer the code for a second.
    #Somehow, the implicit_wait function does not work in this case...
    time.sleep(1)
    pop_ups = driver.find_elements(By.ID, 'didomi-notice-disagree-button')
    if pop_ups:
        pop_ups[0].click()
    time.sleep(3)


    #Next, we get the list of all the containers of movie info
    list_of_movies_selector = driver.find_element(By.ID, 'cinema-schedule')
    list_of_movies = list_of_movies_selector.find_elements(By.CLASS_NAME, 'col-lg-14')
    
    #Now that we have the list of movies, we will go in each one of them, and access their title (only their title for now)
    films_a_l_affiche = []

    if list_of_movies:
        for movie in list_of_movies:
            
            movie_title_container = movie.find_element(By.CLASS_NAME, "card-screening__right")
            movie_title = movie_title_container.find_element(By.TAG_NAME, "a")
            title = movie_title.text
            print(title)
    
            films_a_l_affiche.append({'title': title})
    
    if films_a_l_affiche:
        return films_a_l_affiche
        
    else:
        print("Pas de film à l'affiche")
        return([])


def Pathe():
    st.write("Voici les cinémas Pathé proches de chez vous, selon l'adresse renseignée en page d'accueil :")
    cinemasProchesPathe = st.session_state.cinemasProchesPathe
    st.dataframe(cinemasProchesPathe)
    url= st.text_input("Entrez l'URL du cinéma Pathé : ", key="question_input")
    if st.button("Lancer la recherche"):
        driver = webdriver.Chrome()
        driver.set_window_size(1920,1080)
        if url:
            films = get_movies_pathe(driver, url)
            films_updated = update_list_of_screenings(driver, films)
            films_pathe = pd.DataFrame(films_updated).sort_values(by = "ratings", ascending= False)
            driver.quit()
            st.dataframe(films_pathe)
        else: 
            st.write("Aucune URL entrée")




#-----------------------------------------------------------------------------

if app_en_cour == 'Main page' : main_page()
if app_en_cour == 'UGC' : UGC()
if app_en_cour == "CGR": CGR()
if app_en_cour == "Pathé": Pathe()
if app_en_cour == "MK2": MK2()


