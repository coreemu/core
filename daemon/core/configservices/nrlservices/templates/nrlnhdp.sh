<%
  ifaces = "-i " + " -i ".join(ifnames)
  smf = ""
  if has_smf:
    smf = "-flooding ecds -smfClient %s_smf" % node.name
%>
nrlnhdp -l /var/log/nrlnhdp.log -rpipe ${node.name}_nhdp ${smf} ${ifaces}
