<?xml version="1.0" encoding="utf-8"?>
<!--
 ! Transform documentation directory into presentable XHTML
 !-->
<xsl:transform version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
 xmlns:doc="https://fault.io/xml/documentation"
 xmlns="http://www.w3.org/1999/xhtml"
 exclude-result-prefixes="xsl doc">

 <xsl:import href="xhtml.xsl"/>
 <xsl:param name="prefix"><xsl:text>/</xsl:text></xsl:param>
 <xsl:param name="long.args.limit" select="65"/>

 <xsl:output method="xml" encoding="utf-8" indent="yes"
  doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"
  doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"/>

 <xsl:template match="/">
  <html>
   <head>
    <title>
     Module Documentation
    </title>
    <link rel="stylesheet" type="text/css" href="python.css"/>
   </head>
   <body>
    <div class="content">
     <xsl:apply-templates select="doc:*"/>
    </div>
   </body>
  </html>
 </xsl:template>

</xsl:transform>
<!--
 ! vim: et:sw=1:ts=1
 !-->
