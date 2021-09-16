import json
import re
import socket
from urllib.parse import unquote

import requests


with open("RU.txt", "r", encoding="utf-8") as fi:
    geo_data = [i.split("\t") for i in fi.readlines()]


names_of_columns = {
    0: "geonameid",
    1: "name",
    2: "asciiname",
    3: "alternatenames",
    4: "latitude",
    5: "longitude",
    6: "feature class",
    7: "feature code",
    8: "country code",
    9: "cc2",
    10: "admin1 code",
    11: "admin2 code",
    12: "admin3 code",
    13: "admin4 code",
    14: "population",
    15: "elevation",
    16: "dem",
    17: "timezone",
    18: "modification date",
}


class GeoPlace:
    """Accept geo_identifier - it may be geo id or geo name; form instance of GeoPlace"""

    def __init__(self, geo_identifier):
        self.geo_identifier = str(geo_identifier)

        if self.geo_identifier.isalpha():
            self.geo_id = self.convert_geo_identifier_to_geo_id()
        elif self.geo_identifier.isdigit():
            self.geo_id = geo_identifier

        self.city_info = self.get_info()
        self.city_name = self.city_info.split("<ul>")[3].split(":")[-1]
        self.city_latitude = (
            self.city_info.split("<ul>")[5].split(":")[-1].replace("</ul>", "")
        )
        self.city_longitude = (
            self.city_info.split("<ul>")[6].split(":")[-1].replace("</ul>", "")
        )
        self.city_gmt_offset = self.get_gmt_offset()

    def convert_geo_identifier_to_geo_id(self) -> str:
        """Get geo_identifier and return city id"""

        name = self.geo_identifier
        geo_info = dict()
        name_coincidence = dict()
        try:
            for geo_place in geo_data:
                if re.findall(name.lower(), geo_place[3].lower()):
                    name_coincidence[geo_place[3]] = geo_place[-5]
                    geo_info[geo_place[3]] = geo_place

            # finding top population value for city
            top_population = sorted(
                name_coincidence.values(), key=lambda x: float(x), reverse=True
            )[0]

            city_name, city_id = None, None
            for name, population in name_coincidence.items():
                if population == top_population:
                    city_name = name
            for name in geo_info:
                if city_name == name:
                    city_id = geo_info[name][0]
            return city_id

        except (ValueError, Exception):
            print("There is not place in DB with such name...")

    def get_info(self) -> str:
        """Create html page with info"""

        for geo_location in geo_data:
            if geo_location[0] == self.geo_id:
                html_page = ""
                for column_name, attribute in zip(
                    names_of_columns.values(), geo_location
                ):
                    html_page += (
                        "<ul>" + str(column_name) + ": " + str(attribute) + "</ul>"
                    )
                html_page += 100 * "*" + "<p>"
                return html_page
        else:
            raise ValueError("There is not city with such id")

    def get_gmt_offset(self) -> float:
        """Return gmtOffset using API geonames timezone"""

        base_url = "http://api.geonames.org/timezoneJSON"
        params = {
            "lat": self.city_latitude,
            "lng": self.city_longitude,
            "username": "gogo",
        }
        result = requests.get(url=base_url, params=params)
        result_json = json.loads(result.text)
        gmt_offset = float(result_json["gmtOffset"])

        return gmt_offset


class Server:
    def __init__(self, address="127.0.0.1", port=8000):
        self.address = address
        self.port = port

    def start_server(self) -> None:
        """Run the server until keyboard interrupt"""

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind((self.address, self.port))
            server.listen(5)

            while True:
                print("Server is working...")
                client_socket, address = server.accept()
                data = client_socket.recv(1024).decode("utf-8")

                content = self.load_page_from_get_request(data)
                client_socket.send(content)
                client_socket.shutdown(socket.SHUT_WR)
        except KeyboardInterrupt:
            server.close()
            print("Shutdown it...")

    @staticmethod
    def load_page_from_get_request(request_data: str) -> bytes:
        """Get request and return encoded html"""

        hdrs = (
            "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n".encode(
                "utf-8"
            )
        )
        hdrs_404 = (
            "HTTP/1.1 404 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n".encode(
                "utf-8"
            )
        )

        try:

            # processing of case of comparing two cities by cities names
            if re.findall(r"/compare_two_cities/.+&.+", request_data.split(" ")[1]):
                geo_names = list(
                    map(unquote, request_data.split(" ")[1].split("/")[-1].split("&"))
                )
                city_1 = GeoPlace(geo_names[0])
                city_2 = GeoPlace(geo_names[1])

                if city_1.city_latitude > city_2.city_latitude:
                    north_city_info = (
                        f"{city_1.city_name} is located north of {city_2.city_name}"
                    )
                else:
                    north_city_info = (
                        f"{city_2.city_name} is located north of {city_1.city_name}"
                    )

                if city_1.city_gmt_offset == city_2.city_gmt_offset:
                    timezone_info = "Timezones are the same"
                else:
                    timezone_info = "Timezones are different"

                timezone_difference = city_1.city_gmt_offset - city_2.city_gmt_offset

                response = (
                    city_1.city_info
                    + city_2.city_info
                    + "<h1>"
                    + north_city_info
                    + "<h1>"
                    + timezone_info
                    + "<h1>"
                    + f"Timezone difference (city1 - city2) is {timezone_difference} hour(s)"
                ).encode("utf-8")

                return hdrs + response

            # processing of case of getting info about place by geo id
            elif re.findall(r"/get_info/\d+", request_data.split(" ")[1]):
                geo_name_id = request_data.split(" ")[1].split("/")[-1]
                try:
                    city = GeoPlace(geo_name_id)
                    response = city.city_info.encode("utf-8")
                    return hdrs + response
                except (ValueError, Exception):
                    return hdrs_404 + "GeoNameID not found...".encode("utf-8")

            # home html
            elif request_data.split(" ")[1].split("/")[-1] == "":
                return (
                    hdrs
                    + "Welcome to base page of web-service. Check readme.md to quick start".encode(
                        "utf-8"
                    )
                )

            # page not found
            else:
                return (
                    hdrs_404
                    + "Page not found. Please, check out readme.md file".encode("utf-8")
                )
        # server error
        except (ValueError, Exception):
            print("Server error")
            return hdrs_404 + "Some exception on server. Check readme.md".encode(
                "utf-8"
            )


if __name__ == "__main__":
    print("Now go to: http://127.0.0.1:8000")
    my_server = Server()
    my_server.start_server()
