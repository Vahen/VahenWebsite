import concurrent.futures
import requests
from flask import render_template, make_response, request, send_file, after_this_request
from application.webcrawler import webcrawler_bp, webcrawler_source, webcrawler_toolbox

# Necessaire pour avoir les info au moment du submit
download_links = []


# Format du dictionnaire pour 1 lien#
# {
#     'link':"liensVersRessource",
#     'name':"nomDeRessource",
#     'isVisited':True # Ou false, si le lien a déjà été visité ou non pendant le parcours
# }

############################################
#              WebCrawler                  #
############################################

# On ne pas écrire "List[Dict[str, str, bool]]" pour le typing -> Erreur au lancement
# Parse le site web et récupère les liens
def web_crawler_parse_website(base_url: str, domain: str, depth: int, extensions):  # -> List[Link]:
    list_link = webcrawler_source.construct_tree_link(base_url, depth, download_links, domain, extensions)
    return webcrawler_toolbox.keep_unique_ordered(list_link)


@webcrawler_bp.route("/webcrawler", methods=['GET', 'POST'])
def web_crawler():
    errors = []
    results = {}
    url = ""
    if request.method == "POST":
        try:
            base_url = request.form['url']
            if not webcrawler_source.link_check(base_url):
                errors.append(
                    "Unable to get URL. Please make sure it's valid and try again."
                )
                return make_response(render_template("webcrawler.html", errors=errors), 200)
            r = requests.get(base_url)
            url = base_url
        except:
            errors.append(
                "Unable to get URL. Please make sure it's valid and try again."
            )
            return make_response(render_template("webcrawler.html", errors=errors), 200)
        if r:
            domain = base_url.split("/")[2]
            extensions_string = request.form['extensions']
            extensions = []
            if extensions_string:
                extensions_string = extensions_string.replace(" ", "")
                extensions = extensions_string.split(";")
            depth = int(request.form['depth'])
            # Afin de ne pas paralyser le serveur, on fera la recolte des liens dans un thread à part
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(web_crawler_parse_website, base_url, domain, depth, extensions)
                results = future.result()
                global download_links
                download_links = results
    if results:
        return make_response(render_template("webcrawler.html", results=results), 200)
    else:
        return make_response(render_template("webcrawler.html", url=url), 200)


def web_crawler_download_annexe(download_folder: str):
    webcrawler_source.download_all(download_links)
    return webcrawler_toolbox.zipdir(download_folder)


@webcrawler_bp.route("/webcrawlerDownload", methods=['POST'])
def web_crawler_download():
    download_folder = "./download"
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(web_crawler_download_annexe, download_folder)
        memory_file = future.result()

        @after_this_request
        def remove_file(response):
            webcrawler_toolbox.remove_directory_and_all_files_in(download_folder)
            return response

        return send_file(memory_file, attachment_filename='files.zip', as_attachment=True)
