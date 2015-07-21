<?xml version="1.0" encoding="utf-8"?>
<!--
 ! Transform project documentation into simple XHTML
 !-->
<xsl:transform version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
 xmlns:xl="http://www.w3.org/1999/xlink"
 xmlns:set="http://exslt.org/sets"
 xmlns:str="http://exslt.org/strings"
 xmlns:exsl="http://exslt.org/common"
 xmlns:func="http://exslt.org/functions"
 xmlns:doc="https://fault.io/xml/documentation"
 xmlns="http://www.w3.org/1999/xhtml"
 exclude-result-prefixes="set str exsl func xl xsl doc"
>
 <xsl:param name="prefix"><xsl:text>/</xsl:text></xsl:param>
 <xsl:param name="long.args.limit" select="60"/>

 <!-- arguably configuration -->
 <xsl:variable name="functions_title" select="'functions'"/>
 <xsl:variable name="classes_title" select="'classes'"/>
 <xsl:variable name="methods_title" select="'methods'"/>
 <xsl:variable name="static_methods_title" select="'static methods'"/>
 <xsl:variable name="class_methods_title" select="'class methods'"/>
 <xsl:variable name="properties_title" select="'properties'"/>
 <xsl:variable name="class_data_title" select="'class data'"/>
 <xsl:variable name="data_title" select="'data'"/>
 <xsl:variable name="imports_title" select="'imports'"/>

 <!-- Used in the output to denote the beginning -->
 <xsl:variable name="class_keyword" select="'class'"/>
 <xsl:variable name="function_keyword" select="'def'"/>
 <xsl:variable name="method_keyword" select="$function_keyword"/>

 <xsl:variable name="arg.sep"><span class="separator">,</span></xsl:variable>
 <xsl:variable name="arg.assignment"><span class="assignment">=</span></xsl:variable>

 <xsl:template match="doc:doc">
  <div class="doc">
   <xsl:value-of select="text()"/>
  </div>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:none">
  <span class="python.type.none"><xsl:value-of select="'None'"/></span>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:true">
  <span class="python.type.bool"><xsl:value-of select="'True'"/></span>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:false">
  <span class="python.type.bool"><xsl:value-of select="'False'"/></span>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:integer">
  <span class="python.type.integer"><xsl:value-of select="text()"/></span>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:real">
  <span class="python.type.real"><xsl:value-of select="text()"/></span>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:string">
  <span class="python.type.string">"<xsl:value-of select="text()"/>"</span>
 </xsl:template>

 <xsl:template mode="python.inline.data" match="doc:function"><span class="python.type.function"><xsl:value-of select="@name"/></span></xsl:template>

 <xsl:template name="setlen">
  <xsl:param name="value" select="0"/>
  <xsl:param name="nodes"/>

  <xsl:choose>
   <xsl:when test="count($nodes) > 1">
    <xsl:call-template name="setlen">
     <xsl:with-param name="value"
      select="$value + string-length($nodes[position() = 1])"/>
     <xsl:with-param name="nodes"
      select="exsl:node-set($nodes[position() > 1])"/>
    </xsl:call-template>
   </xsl:when>
   <xsl:otherwise>
    <xsl:copy-of select="$value + string-length($nodes[position()=1])"/>
   </xsl:otherwise>
  </xsl:choose>
 </xsl:template>

 <xsl:template match="doc:positional">
  <span class="positional">
   <span class="positional.name"><xsl:value-of select="@name"/></span>

   <xsl:if test="doc:default">
    <span class="assignment">=</span><span class="positional.default"><xsl:apply-templates mode="python.inline.data" select="doc:default/doc:*"/></span>
   </xsl:if>
  </span><xsl:copy-of select="$arg.sep"/>
 </xsl:template>

 <xsl:template match="doc:keyword">
  <span class="keyword">
   <span class="keyword.name"><xsl:value-of select="@name"/></span>

   <xsl:if test="doc:default">
    <span class="assignment">=</span><span class="keyword.default"><xsl:apply-templates mode="python.inline.data" select="doc:default/doc:*"/></span>
   </xsl:if>
  </span><xsl:copy-of select="$arg.sep"/>
 </xsl:template>

 <xsl:template match="doc:signature">
  <span class="signature">
   <xsl:apply-templates select="doc:positional"/>
   <xsl:if test="@varargs">
    <span class="positional">
     <span class="positional.varying.signature">*</span>
     <span class="varying"><xsl:value-of select="@varargs"/></span>
    </span><xsl:copy-of select="$arg.sep"/>
   </xsl:if>

   <xsl:apply-templates select="doc:keyword"/>
   <xsl:if test="@varkw">
    <span class="keyword">
     <span class="keyword.varying.signature">**</span>
     <span class="varying"><xsl:value-of select="@varkw"/></span>
    </span><xsl:copy-of select="$arg.sep"/>
   </xsl:if>
  </span>
 </xsl:template>

 <xsl:template mode="python.bases" match="doc:type">
  <span class="python.type"><xsl:value-of select="@name"/></span>
  <span class="separator">,</span>
 </xsl:template>

 <xsl:template match="doc:bases">
  <span class="python.bases">
   <xsl:apply-templates mode="python.bases" select="doc:type"/>
  </span>
 </xsl:template>

 <xsl:template match="doc:data">
  <div class="data" title="{./doc:type/doc:ref/@path}">
   <xsl:if test="@xml:id">
    <xsl:attribute name="xml:id"><xsl:value-of select="@xml:id"/></xsl:attribute>
   </xsl:if>
   <span class="name"><xsl:value-of select="@doc:identifier"/></span>
   <xsl:text> = </xsl:text>
  </div>
 </xsl:template>

 <xsl:template match="doc:import">
  <div class="import">
   <span class="keyword">import</span>
   <xsl:text> </xsl:text>
   <a class="import">
    <xsl:if test="@source = 'builtin'">
     <xsl:attribute name="href"><xsl:value-of select="concat('https://docs.python.org/3/library/', @identifier, '.html')"/></xsl:attribute>
    </xsl:if>
    <span class="path">
     <xsl:value-of select="@identifier"/>
    </span>
    <xsl:if test="@doc:identifier and @doc:identifier != ./doc:ref/@path">
     <xsl:text> as </xsl:text>
     <span class="name"><xsl:value-of select="@doc:identifier"/></span>
    </xsl:if>
   </a>
  </div>
 </xsl:template>

 <xsl:template match="doc:property">
  <xsl:variable name="name" select="@identifier"/>
  <xsl:variable name="path" select="@xml:id"/>
  <div class="property">
   <div class="title">
    <span class="keyword">property</span>
    <xsl:text> </xsl:text>
    <span class="title"><xsl:value-of select="$name"/></span>
   </div>
   <xsl:apply-templates select="./doc:doc"/>
  </div>
 </xsl:template>

 <xsl:template match="doc:function|doc:method">
  <xsl:variable name="name" select="@identifier"/>
  <xsl:variable name="path" select="@xml:id"/>
  <xsl:variable name="class_name" select="../@identifier"/>

  <div class="{local-name()}">
   <xsl:attribute name="xml:id"><xsl:value-of select="@xml:id"/></xsl:attribute>
   <div class="title">
    <span class="keyword">def</span>
    <xsl:text> </xsl:text>
    <span class="title">
     <xsl:if test="(..)[local-name()='class']">
      <span class="class-method-path"><xsl:value-of select="$class_name"/>.</span>
     </xsl:if>
     <xsl:value-of select="$name"/>
    </span>
    <span class="python.parameter.area">
     <span class="parameters.open">(</span>
     <xsl:apply-templates select="doc:signature"/>
     <span class="parameters.close">):</span>
    </span>
   </div>
   <xsl:apply-templates select="./doc:doc"/>
  </div>
 </xsl:template>

 <xsl:template match="doc:class">
  <xsl:variable name="name" select="@identifier"/>
  <xsl:variable name="path" select="@xml:id"/>

  <div class="class" id="{$path}">
   <div class="title">
    <span class="keyword"><xsl:value-of select="$class_keyword"/></span>
    <xsl:text> </xsl:text>
    <span class="title"><xsl:value-of select="$name"/></span>
    <span class="python.parameter.area">
     <xsl:text>(</xsl:text>
      <xsl:apply-templates select="doc:bases"/>
     <xsl:text>):</xsl:text>
    </span>
   </div>

   <xsl:apply-templates select="./doc:doc"/>

   <div class="content">
    <xsl:if test="./doc:import">
     <div class="imports">
      <div class="head">
       <span class="title"><xsl:value-of select="$imports_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:import"/>
     </div>
    </xsl:if>

    <xsl:if test="./doc:method[@type='class' and doc:doc]">
     <div class="class_methods">
      <div class="head">
       <span class="title"><xsl:value-of select="$class_methods_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:method[@type='class' and doc:doc]"/>
     </div>
    </xsl:if>
    <xsl:if test="./doc:method[not(@type) and doc:doc]">
     <div class="methods">
      <div class="head">
       <span class="title"><xsl:value-of select="$methods_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:method[not(@type) and doc:doc]"/>
     </div>
    </xsl:if>
    <xsl:if test="./doc:method[@type='static' and doc:doc]">
     <div class="static_methods">
      <div class="head">
       <span class="title"><xsl:value-of select="$static_methods_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:method[@type='static' and ./doc:doc]"/>
     </div>
    </xsl:if>
    <xsl:if test="./doc:property[doc:doc]">
     <div class="properties">
      <div class="head">
       <span class="title"><xsl:value-of select="$properties_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:property"/>
     </div>
    </xsl:if>
    <xsl:if test="./doc:data">
     <div class="datas">
      <div class="head">
       <span class="title"><xsl:value-of select="$class_data_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:data"/>
     </div>
    </xsl:if>
   </div>
  </div>
 </xsl:template>

 <xsl:template match="doc:module">
  <xsl:variable name="name" select="@identifier"/>
  <xsl:variable name="path" select="@xml:id"/>
  <div class="module">
   <div class="title">
    <span class="keyword">module</span>
    <xsl:text> </xsl:text>
    <xsl:value-of select="$name"/>
   </div>

   <xsl:apply-templates select="./doc:doc"/>

   <div class="content">
    <xsl:if test="./doc:import">
     <div class="imports">
      <div style="display: none;" class="head">
       <span class="title"><xsl:value-of select="$imports_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:import"/>
     </div>
    </xsl:if>

    <xsl:if test="./doc:data">
     <div class="data">
      <div style="display: none;" class="head">
       <span class="title"><xsl:value-of select="$data_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:data"/>
     </div>
    </xsl:if>

    <xsl:if test="./doc:function[doc:doc]">
     <div class="functions">
      <div style="display: none;" class="head">
       <span class="title"><xsl:value-of select="$functions_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:function"/>
     </div>
    </xsl:if>

    <xsl:if test="./doc:class[doc:doc]">
     <div class="classes">
      <div style="display: none;" class="head">
       <span class="title"><xsl:value-of select="$classes_title"/></span>
      </div>
      <xsl:apply-templates select="./doc:class[doc:doc]"/>
     </div>
    </xsl:if>
   </div>
  </div>
 </xsl:template>

 <xsl:template match="doc:unit">
 </xsl:template>

 <xsl:template match="doc:factor">
  <xsl:apply-templates select="./doc:module"/>
 </xsl:template>
</xsl:transform>
<!--
 ! vim: et:sw=1:ts=1
 !-->
