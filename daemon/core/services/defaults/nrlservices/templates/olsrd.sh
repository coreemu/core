<%
  ifaces = "-i " + " -i ".join(ifnames)
%>
olsrd ${ifaces}
