<%
  interfaces = "-i " + " -i ".join(ifnames)
%>
olsrd ${interfaces}
