"""
core node services
"""
import tkinter as tk
from tkinter import messagebox

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


class NodeServices:
    def __init__(self):
        self.core_groups = []
        self.service_to_config = None

        self.top = tk.Toplevel()
        self.top.title("Node services")
        self.config_frame = tk.Frame(self.top)
        self.config_frame.grid()
        self.draw_group()
        self.group_services()
        self.current_services()
        self.node_service_options()

    def display_group_services(self, group_name):
        group_services_frame = self.config_frame.grid_slaves(row=0, column=1)[0]
        listbox = group_services_frame.grid_slaves(row=1, column=0)[0]
        listbox.delete(0, tk.END)
        for s in DEFAULT_GROUP_SERVICES[group_name]:
            listbox.insert(tk.END, s)
        for i in range(listbox.size()):
            listbox.itemconfig(i, selectbackground="white")

    def group_select(self, event):
        listbox = event.widget
        cur_selection = listbox.curselection()
        if cur_selection:
            s = listbox.get(listbox.curselection())
            self.display_group_services(s)

    def draw_group(self):
        """
        draw the group tab

        :return: nothing
        """
        f = tk.Frame(self.config_frame)

        lbl = tk.Label(f, text="Group")
        lbl.grid()

        sb = tk.Scrollbar(f, orient=tk.VERTICAL)
        sb.grid(row=1, column=1, sticky=tk.S + tk.N)

        listbox = tk.Listbox(
            f,
            selectmode=tk.SINGLE,
            yscrollcommand=sb.set,
            relief=tk.FLAT,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )

        for grp in CORE_DEFAULT_GROUPS:
            listbox.insert(tk.END, grp)
        for i in range(0, listbox.size()):
            listbox.itemconfig(i, selectbackground="white")
        listbox.grid(row=1, column=0)

        sb.config(command=listbox.yview)
        f.grid(padx=3, pady=3)
        listbox.bind("<<ListboxSelect>>", self.group_select)

    def group_service_select(self, event):
        print("select group service")
        listbox = event.widget
        cur_selection = listbox.curselection()
        if cur_selection:
            s = listbox.get(listbox.curselection())
            self.service_to_config = s
        else:
            self.service_to_config = None

    def group_services(self):
        f = tk.Frame(self.config_frame)
        lbl = tk.Label(f, text="Group services")
        lbl.grid()

        sb = tk.Scrollbar(f, orient=tk.VERTICAL)
        sb.grid(row=1, column=1, sticky=tk.S + tk.N)

        listbox = tk.Listbox(
            f,
            selectmode=tk.SINGLE,
            yscrollcommand=sb.set,
            relief=tk.FLAT,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )
        listbox.grid(row=1, column=0)
        sb.config(command=listbox.yview)
        f.grid(padx=3, pady=3, row=0, column=1)

        listbox.bind("<<ListboxSelect>>", self.group_service_select)

    def current_services(self):
        f = tk.Frame(self.config_frame)
        lbl = tk.Label(f, text="Current services")
        lbl.grid()

        sb = tk.Scrollbar(f, orient=tk.VERTICAL)
        sb.grid(row=1, column=1, sticky=tk.S + tk.N)

        listbox = tk.Listbox(
            f,
            selectmode=tk.MULTIPLE,
            yscrollcommand=sb.set,
            relief=tk.FLAT,
            highlightbackground="#b3b3b3",
            highlightcolor="#b3b3b3",
            highlightthickness=0.5,
            bd=0,
        )
        listbox.grid(row=1, column=0)
        sb.config(command=listbox.yview)
        f.grid(padx=3, pady=3, row=0, column=2)

    def config_service(self):
        if self.service_to_config is None:
            messagebox.showinfo("CORE info", "Choose a service to configure.")
        else:
            print(self.service_to_config)

    def node_service_options(self):
        f = tk.Frame(self.top)
        b = tk.Button(f, text="Connfigure", command=self.config_service)
        b.grid(row=0, column=0)
        b = tk.Button(f, text="Apply")
        b.grid(row=0, column=1)
        b = tk.Button(f, text="Cancel", command=self.top.destroy)
        b.grid(row=0, column=2)
        f.grid(sticky=tk.E)
