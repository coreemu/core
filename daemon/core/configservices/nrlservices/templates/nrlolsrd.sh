<%
  smf = ""
  if has_smf:
    smf = "-flooding s-mpr -smfClient %s_smf" % node.name
  zebra = ""
  if has_zebra:
    zebra = "-z"
%>
nrlolsrd -i ${ifname} -l /var/log/nrlolsrd.log -rpipe ${node.name}_olsr ${smf} ${zebra}
