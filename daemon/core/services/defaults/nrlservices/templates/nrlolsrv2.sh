<%
  ifaces = "-i " + " -i ".join(ifnames)
  smf = ""
  if has_smf:
    smf = "-flooding ecds -smfClient %s_smf" % node.name
%>
nrlolsrv2 -l /var/log/nrlolsrv2.log -rpipe ${node.name}_olsrv2 -p olsr ${smf} ${ifaces}
