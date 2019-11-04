"""
core node services
"""
import tkinter as tk
from tkinter import messagebox

from coretk.dialogs.dialog import Dialog

CORE_DEFAULT_GROUPS = ["EMANE", "FRR", "ProtoSvc", "Quagga", "Security", "Utility"]
DEFAULT_GROUP_RADIO_VALUE = {
    "EMANE": 1,
    "FRR": 2,
    "ProtoSvc": 3,
    "Quagga": 4,
    "Security": 5,
    "Utility": 6,
}
DEFAULT_GROUP_SERVICES = {
    "EMANE": ["transportd"],
    "FRR": [
        "FRRBable",
        "FRRBGP",
        "FRROSPFv2",
        "FRROSPFv3",
        "FRRpimd",
        "FRRRIP",
        "FRRRIPNG",
        "FRRzebra",
    ],
    "ProtoSvc": ["MGEN_Sink", "MgenActor", "SMF"],
    "Quagga": [
        "Babel",
        "BGP",
        "OSPFv2",
        "OSPFv3",
        "OSPFv3MDR",
        "RIP",
        "RIPNG",
        "Xpimd",
        "zebra",
    ],
    "Security": ["Firewall", "IPsec", "NAT", "VPNClient", "VPNServer"],
    "Utility": [
        "atd",
        "DefaultMulticastRoute",
        "DefaultRoute",
        "DHCP",
        "DHCPClient",
        "FTP",
        "HTTP",
        "IPForward ",
        "pcap",
        "radvd",
        "SSH",
        "StaticRoute",
        "ucarp",
        "UserDefined",
    ],
}


class NodeServicesDialog(Dialog):
    def __init__(self, master, app, canvas_node):
        super().__init__(master, app, "Node Services", modal=True)
        self.canvas_node = canvas_node
        self.core_groups = []
        self.service_to_config = None
        self.config_frame = None
        self.draw()

    def draw(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.config_frame = tk.Frame(self)
        self.config_frame.columnconfigure(0, weight=1)
        self.config_frame.columnconfigure(1, weight=1)
        self.config_frame.columnconfigure(2, weight=1)
        self.config_frame.rowconfigure(0, weight=1)
        self.config_frame.grid(row=0, column=0, sticky="nsew")
        self.draw_group()
        self.draw_services()
        self.draw_current_services()
        self.draw_buttons()

    def draw_group(self):
        """
        draw the group tab

        :return: nothing
        """
        frame = tk.Frame(self.config_frame)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")

        label = tk.Label(frame, text="Group")
        label.grid(row=0, column=0, sticky="ew")

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.grid(row=1, column=1, sticky="ns")

        listbox = tk.Listbox(
            frame,
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            highlightthickness=0.5,
            bd=0,
        )
        listbox.grid(row=1, column=0, sticky="nsew")
        listbox.bind("<<ListboxSelect>>", self.handle_group_change)

        for group in CORE_DEFAULT_GROUPS:
            listbox.insert(tk.END, group)

        scrollbar.config(command=listbox.yview)

    def draw_services(self):
        frame = tk.Frame(self.config_frame)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")

        label = tk.Label(frame, text="Group services")
        label.grid(row=0, column=0, sticky="ew")

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.grid(row=1, column=1, sticky="ns")

        listbox = tk.Listbox(
            frame,
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            highlightthickness=0.5,
            bd=0,
        )
        listbox.grid(row=1, column=0, sticky="nsew")
        listbox.bind("<<ListboxSelect>>", self.handle_service_change)

        scrollbar.config(command=listbox.yview)

    def draw_current_services(self):
        frame = tk.Frame(self.config_frame)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.grid(row=0, column=2, padx=3, pady=3, sticky="nsew")

        label = tk.Label(frame, text="Current services")
        label.grid(row=0, column=0, sticky="ew")

        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.grid(row=1, column=1, sticky="ns")

        listbox = tk.Listbox(
            frame,
            selectmode=tk.MULTIPLE,
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            highlightthickness=0.5,
            bd=0,
        )
        listbox.grid(row=1, column=0, sticky="nsew")

        scrollbar.config(command=listbox.yview)

    def draw_buttons(self):
        frame = tk.Frame(self)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=1, column=0, sticky="ew")

        button = tk.Button(frame, text="Configure", command=self.click_configure)
        button.grid(row=0, column=0, sticky="ew")

        button = tk.Button(frame, text="Apply")
        button.grid(row=0, column=1, sticky="ew")

        button = tk.Button(frame, text="Cancel", command=self.destroy)
        button.grid(row=0, column=2, sticky="ew")

    def handle_group_change(self, event):
        listbox = event.widget
        cur_selection = listbox.curselection()
        if cur_selection:
            s = listbox.get(listbox.curselection())
            self.display_group_services(s)

    def display_group_services(self, group_name):
        group_services_frame = self.config_frame.grid_slaves(row=0, column=1)[0]
        listbox = group_services_frame.grid_slaves(row=1, column=0)[0]
        listbox.delete(0, tk.END)
        for s in DEFAULT_GROUP_SERVICES[group_name]:
            listbox.insert(tk.END, s)

    def handle_service_change(self, event):
        print("select group service")
        listbox = event.widget
        cur_selection = listbox.curselection()
        if cur_selection:
            s = listbox.get(listbox.curselection())
            self.service_to_config = s
        else:
            self.service_to_config = None

    def click_configure(self):
        if self.service_to_config is None:
            messagebox.showinfo("CORE info", "Choose a service to configure.")
        else:
            print(self.service_to_config)
