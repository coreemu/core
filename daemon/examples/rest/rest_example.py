import pprint
import sys
import time

import requests


class CoreRestClient(object):
    def __init__(self, address):
        self.base_url = "http://%s" % address

    def _create_url(self, path):
        return "%s%s" % (self.base_url, path)

    def _delete(self, path, json_data=None):
        url = self._create_url(path)
        print "DELETE: %s" % url
        response = requests.delete(url, json=json_data)
        response_json = response.json()
        pprint.pprint(response_json)
        return response_json

    def _post(self, path, json_data=None):
        url = self._create_url(path)
        print "POST: %s" % url
        response = requests.post(url, json=json_data)
        response_json = response.json()
        pprint.pprint(response_json)
        return response_json

    def _put(self, path, json_data=None):
        url = self._create_url(path)
        print "PUT: %s" % url
        response = requests.put(url, json=json_data)
        response_json = response.json()
        pprint.pprint(response_json)
        return response_json

    def _get(self, path):
        url = self._create_url(path)
        print "GET: %s" % url
        response = requests.get(url)
        response_json = response.json()
        pprint.pprint(response_json)
        return response_json

    def create_session(self):
        return self._post("/sessions")

    def get_sessions(self):
        return self._get("/sessions")

    def get_session(self, session_id):
        return self._get("/sessions/%s" % session_id)

    def delete_session(self, session_id):
        return self._delete("/sessions/%s" % session_id)

    def set_state(self, session_id, state):
        return self._put("/sessions/%s/state" % session_id, json_data={"state": state})

    def add_node(self, session_id, options=None):
        return self._post("/sessions/%s/nodes" % session_id, json_data=options)

    def delete_node(self, session_id, node_id):
        return self._delete("/sessions/%s/nodes/%s" % (session_id, node_id))

    def get_node(self, session_id, node_id):
        return self._get("/sessions/%s/nodes/%s" % (session_id, node_id))

    def get_node_links(self, session_id, node_id):
        return self._get("/sessions/%s/nodes/%s/links" % (session_id, node_id))

    def add_link(self, session_id, link):
        return self._post("/sessions/%s/links" % session_id, json_data=link)

    def delete_link(self, session_id, link):
        return self._delete("/sessions/%s/links" % session_id, json_data=link)


def main():
    address = sys.argv[1]
    client = CoreRestClient(address)

    # create session
    create_response = client.create_session()
    session_id = create_response["id"]

    # query all sessions
    client.get_sessions()

    # query session
    client.get_session(session_id)

    # set state to CONFIGURATION
    client.set_state(session_id, 2)

    # create nodes for small switch networkW
    node_one_response = client.add_node(session_id)
    node_one_id = node_one_response["id"]
    node_two_response = client.add_node(session_id)
    node_two_id = node_two_response["id"]
    switch_options = {
        "type": 4
    }
    switch_node_response = client.add_node(session_id, switch_options)
    switch_id = switch_node_response["id"]

    # link nodes to switch
    link = {
        "node_one": node_one_id,
        "node_two": switch_id,
        "interface_one": {
            "id": 0,
            "ip4": "10.0.0.2",
            "ip4mask": 16
        }
    }
    client.add_link(session_id, link)
    link = {
        "node_one": node_two_id,
        "node_two": switch_id,
        "interface_one": {
            "id": 0,
            "ip4": "10.0.0.3",
            "ip4mask": 16
        }
    }
    client.add_link(session_id, link)

    # set state to INSTANTIATION
    client.set_state(session_id, 3)
    time.sleep(3)

    # get node information
    client.get_node(session_id, node_one_id)
    client.get_node(session_id, node_two_id)
    client.get_node(session_id, switch_id)

    # get links informations
    client.get_node_links(session_id, node_one_id)
    client.get_node_links(session_id, node_two_id)
    client.get_node_links(session_id, switch_id)

    # delete links
    delete_link = {
        "node_one": node_one_id,
        "node_two": switch_id,
        "interface_one": 0,
    }
    client.delete_link(session_id, delete_link)
    delete_link = {
        "node_one": node_two_id,
        "node_two": switch_id,
        "interface_one": 0
    }
    client.delete_link(session_id, delete_link)

    # delete nodes
    client.delete_node(session_id, node_one_id)
    client.delete_node(session_id, node_two_id)
    client.delete_node(session_id, switch_id)

    # delete session
    client.delete_session(session_id)

    # query all sessions
    client.get_sessions()


if __name__ == "__main__":
    main()
