from flask import Flask
from flask import request
import mechanize
import bs4
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config["CORS_HEADERS"] = "Content-Type"


def main_clone(url):
    # Browser
    br = mechanize.Browser()

    # Browser options
    br.set_handle_equiv(True)
    br.set_handle_gzip(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)

    # Follows refresh 0 but not hangs on refresh > 0
    br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

    # Want debugging messages?
    # br.set_debug_http(True)
    # br.set_debug_redirects(True)
    # br.set_debug_responses(True)

    # User-Agent (this is cheating, ok?)
    br.addheaders = [
        (
            "User-agent",
            "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1",
        )
    ]
    html = br.open(url).read()
    soup = bs4.BeautifulSoup(html, "html.parser")
    return soup


def clone_with_src(url):
    soup = main_clone(url)
    for script in soup.find_all("script"):
        if script.get("src") != None and script["src"][0] != "h":
            script["src"] = url + script["src"]
    return soup.prettify()


def simple_clone(url):
    return main_clone(url).prettify()


def clone_map(url):
    soup = main_clone(url)
    for script in soup.find_all("script"):
        if script.get("src") != None and script["src"][0] != "h":
            script["src"] = url + script["src"]
    return soup.prettify()


def clone_two_levels(url):
    soup = main_clone(url)
    for script in soup.find_all("script"):
        if script.get("src") != None and script["src"][0] != "h":
            script["src"] = url + script["src"]
    return soup.prettify().replace("window.parent", "window.parent.parent")


@app.route("/")
@cross_origin(
    origin="*", headers=["Content-Type", "Authorization", "access-control-allow-origin"]
)
def hello_world():
    return "Hello, World!"


@app.route("/iframe", methods=["GET"])
@cross_origin(
    origin="*", headers=["Content-Type", "Authorization", "access-control-allow-origin"]
)
def iframe_serving():
    return clone_with_src(request.args.get("url"))


@app.route("/iframe2", methods=["GET"])
@cross_origin(
    origin="*", headers=["Content-Type", "Authorization", "access-control-allow-origin"]
)
def iframe_serving2():
    return clone_two_levels(request.args.get("url"))


@app.route("/simple-iframe", methods=["GET"])
@cross_origin(
    origin="*", headers=["Content-Type", "Authorization", "access-control-allow-origin"]
)
def iframe_simple():
    return simple_clone(request.args.get("url"))


@app.route("/map-iframe", methods=["GET"])
@cross_origin(
    origin="*", headers=["Content-Type", "Authorization", "access-control-allow-origin"]
)
def iframe_map():
    return clone_map(request.args.get("url"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

