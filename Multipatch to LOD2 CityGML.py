#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Import library yang diperlukan
import shapefile as sf
from lxml import etree
import numpy as np
import uuid
import geopandas as gpd
from shapely.geometry import Polygon


# In[2]:


# Directory multipatch bangunan LOD2 Coblong
sfDir = '/Users/veriandi/Desktop/Projects/CityGML Coblong/Multipatch LOD2/Coblong_LOD2'


# In[ ]:


# Directory shapefile persil Coblong
persilDir = '/Users/veriandi/Desktop/Projects/CityGML Coblong/Persil/persil.shp'


# In[3]:


# Membaca file persil dan memasukkannya ke dalam GeoDataFrame
Persil = gpd.read_file(persilDir)
persil = Persil.loc[:, ['NIB', 'geometry']]
persil = persil.to_crs('EPSG:32748')


# In[4]:


# Membaca file multipatch LOD2
# Ekstraksi geometri dan atribut
sfReader = sf.Reader(sfDir)
features = sfReader.shapes()
attributes = sfReader.records()


# In[6]:


# Ekstraksi koordinat XY dan Z yang disimpan dalam list berbeda
FeatXYCoords = []
FeatZCoords = []
for feature in features:
    XYCoords = []
    ZCoords = []
    xy = feature.points
    z = feature.z
    for n in range(len(feature.parts)):
        if n != len(feature.parts)-1:
            PartXYCoords = xy[feature.parts[n]:feature.parts[n+1]]
            PartZCoords = z[feature.parts[n]:feature.parts[n+1]]
            XYCoords.append(PartXYCoords)
            ZCoords.append(PartZCoords)
        elif n == len(feature.parts)-1:
            PartXYCoords = xy[feature.parts[n]:]
            PartZCoords = z[feature.parts[n]:]
            XYCoords.append(PartXYCoords)
            ZCoords.append(PartZCoords)
    FeatXYCoords.append(XYCoords)
    FeatZCoords.append(ZCoords)
    
# Ekstraksi koordinat XY dan Z yang disimpan dalam list yang sama
FeatXYZCoords = []
for i, feature in enumerate(FeatXYCoords):
    XYZFeat = []
    for n, surface in enumerate(feature):
        XYZSurf = []
        for m, xy in enumerate(surface):
            l_coord = list(xy)
            l_coord.append(FeatZCoords[i][n][m])
            t_coord = tuple(l_coord)
            XYZSurf.append(t_coord)
        XYZFeat.append(XYZSurf)
    FeatXYZCoords.append(XYZFeat)


# In[7]:


# Restrukturasi koordinat agar dimiliki urutan koordinat yang benar
# untuk setiap surface
XYZCoords = []
for i, feature in enumerate(FeatXYZCoords):
    featCoords = []
    for n, surface in enumerate(feature):
        partType = features[i].partTypes[n]
        if partType == 2 or partType == 3:
            featCoords.append(surface)
        elif partType == 0:
            for m in range(len(surface)-2):
                newSurf = [surface[m], surface[m+1], surface[m+2], surface[m]]
                featCoords.append(newSurf)
    XYZCoords.append(featCoords)


# In[8]:


# Kalkulasi ketinggian minimum dan maksimum di setiap bangunan
ZMin = []
ZMax = []
for feat in FeatZCoords:
    FeatZ = []
    for surf in feat:
        for z in surf:
            FeatZ.append(z)
    ZMin.append(min(FeatZ))
    ZMax.append(max(FeatZ))


# In[9]:


# Fungsi perhitungan luas
def PolyArea(x,y):
    return 0.5*np.abs(np.dot(x,np.roll(y,1))-np.dot(y,np.roll(x,1)))


# In[10]:


# Klasifikasi semantik menggunakan luas bidang jika diproyeksikan ke 2D
# dan ketinggian rata2 bidang
OutputDict = {}
ID = 0
for i, feature in enumerate(XYZCoords):
    
    ID += 1
    OutputDict['IDLOD2_{}'.format(ID)] = {'Ground':[],'Wall':[],'Roof':[]}
    
    for surface in feature:
        
        SurfXY = []
        SurfZ = []
        for coord in surface:
            xy = (coord[0], coord[1])
            z = (coord[2])
            SurfXY.append(xy)
            SurfZ.append(z)
        x, y = map(list, zip(*SurfXY))
        Area2D = PolyArea(x, y)
        AvgHeight = sum(SurfZ)/len(SurfZ)
        
        if Area2D < 0.1:
            OutputDict['IDLOD2_{}'.format(ID)]['Wall'].append(surface)
        elif Area2D >= 0.1 and (ZMin[i]+2 >= AvgHeight):
            OutputDict['IDLOD2_{}'.format(ID)]['Ground'].append(surface)
        elif Area2D >= 0.1 and (AvgHeight > ZMin[i]+2):
            OutputDict['IDLOD2_{}'.format(ID)]['Roof'].append(surface)


# In[11]:


# Menyimpan GroundSurface ke dalam dictionary
groundSurfs = []
for ID in OutputDict.keys():
    groundSurfs.append(OutputDict[ID]['Ground'])


# In[12]:


# Menyimpan GroundSurface ke dalam GeoDataFrame
# Diperlukan untuk proses spatial join dengan GeoDataFrame persil
# Untuk mendapatkan informasi persil-persil yang berpotongan dengan building footprint setiap bangunan
dfGround = gpd.GeoDataFrame(columns=['geometry'], crs='EPSG:32748')
for i, feature in enumerate(groundSurfs):
    dfSurface = gpd.GeoDataFrame(columns=['geometry'], crs='EPSG:32748')
    for n, surface in enumerate(feature):
        XY = []
        for m, coord in enumerate(surface):
            xycoord = (coord[0], coord[1])
            XY.append(xycoord)
        dfSurface.loc[n] = Polygon(XY)
    dfSurface['constant'] = 0
    diss = dfSurface.dissolve(by='constant')
    dfGround.loc[i] = diss.loc[0]


# In[13]:


# Spatial join building footprint/GroundSurface dengan persil
groundSJoin = gpd.sjoin(dfGround, persil, how="left", op='intersects')


# In[14]:


# Ekstraksi NIB persil yang berpotongan pada setiap building footprint
NIB = {}
for i, row in groundSJoin.iterrows():
    if i not in NIB.keys():
        NIB[i] = [row['NIB']]
    elif i in NIB.keys():
        NIB[i].append(row['NIB'])


# In[70]:


# Mendefinisikan namespace CityGML
ns_base = "http://www.citygml.org/citygml/profiles/base/2.0"
ns_core = "http://www.opengis.net/citygml/2.0"
ns_bldg = "http://www.opengis.net/citygml/building/2.0"
ns_gen = "http://www.opengis.net/citygml/generics/2.0"
ns_gml = "http://www.opengis.net/gml"
ns_xAL = "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
ns_xlink = "http://www.w3.org/1999/xlink"
ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
ns_schemaLocation = "http://www.citygml.org/citygml/profiles/base/2.0 http://schemas.opengis.net/citygml/profiles/base/2.0/CityGML.xsd"

nsmap = {None : ns_base, 'core': ns_core, 'bldg': ns_bldg, 'gen': ns_gen, 'gml': ns_gml, 'xAL': ns_xAL, 'xlink': ns_xlink, 'xsi': ns_xsi}


# In[71]:


# Membuat root element CityGML (CityModel)
CityModel = etree.Element("{%s}CityModel" % ns_core, nsmap=nsmap)
CityModel.set('{%s}schemaLocation' % ns_xsi, ns_schemaLocation)


# In[72]:


# Membuat deskripsi dari file/model
description = etree.SubElement(CityModel, '{%s}description' % ns_gml)
description.text = 'Coblong LOD 2 Buildings'


# In[73]:


# Mendefinisikan fungsi untuk kalkulasi bounding box
def bounding_box(bldg_feat_dict):
    coorX = []
    coorY = []
    coorZ = []
    for ID in bldg_feat_dict.keys():
        for surface in bldg_feat_dict[ID]:
            for coord in surface:
                coorX.append(coord[0])
                coorY.append(coord[1])
                coorZ.append(coord[2])
    lowerCorner = [min(coorX), min(coorY), min(coorZ)]
    upperCorner = [max(coorX), max(coorY), max(coorZ)]
    return lowerCorner, upperCorner


# In[74]:


# Kalkulasi bounding box untuk model
xValues = []
yValues = []
zValues = []
for i, ID in enumerate(OutputDict.keys()):
    lower, upper = bounding_box(OutputDict[ID])
    xValues.append(lower[0])
    xValues.append(upper[0])
    yValues.append(lower[1])
    yValues.append(upper[1])
    zValues.append(lower[2])
    zValues.append(upper[2])
        
lower = [min(xValues), min(yValues), min(zValues)]
upper = [max(xValues), max(yValues), max(zValues)]

crs = 'EPSG:32748'

BoundingBox = etree.SubElement(CityModel, '{%s}boundedBy' % ns_gml)
Envelope = etree.SubElement(BoundingBox, '{%s}Envelope' % ns_gml, srsDimension='3')
Envelope.set('srsName', crs)

lowCorner = etree.SubElement(Envelope, '{%s}lowerCorner' % ns_gml)
lowCorner.text = str(lower[0]) + ' ' + str(lower[1]) + ' ' + str(lower[2])
uppCorner = etree.SubElement(Envelope, '{%s}upperCorner' % ns_gml)
uppCorner.text = str(upper[0]) + ' ' + str(upper[1]) + ' ' + str(upper[2])


# In[75]:


# Mendefinisikan fungsi untuk menulis bidang
def writing_surfaces(surface_geometry, surface_element_name):
    for surface in surface_geometry:
        surf_uuid = 'UUID_' + str(uuid.uuid4()) + '_2'
        boundedBy = etree.SubElement(Building, '{%s}boundedBy' % ns_bldg)
        Surface = etree.SubElement(boundedBy, surface_element_name % ns_bldg)
        Surface.set('{%s}id' % ns_gml, surf_uuid)
        lod2MultiSurface = etree.SubElement(Surface, '{%s}lod2MultiSurface' % ns_bldg)
        MultiSurface = etree.SubElement(lod2MultiSurface, '{%s}MultiSurface' % ns_gml)
        surfaceMember = etree.SubElement(MultiSurface, '{%s}surfaceMember' % ns_gml)
        Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
        Polygon.set('{%s}id' % ns_gml, surf_uuid + '_poly')
        exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
        LinearRing = etree.SubElement(exterior, '{%s}LinearRing' % ns_gml)
        posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
        coordinates = ''
        copy = ''
        for coordinate in surface:
            coordinates = copy + str(coordinate[0]) + ' ' + str(coordinate[1]) + ' ' + str(coordinate[2]) + ' '
            copy = coordinates
        posList.text = coordinates[:-1]
        solid_link = etree.SubElement(CompositeSurface, '{%s}surfaceMember' % ns_gml)
        solid_link.set('{%s}href' % ns_xlink, '#' + surf_uuid + '_poly')


# In[76]:


# Iterasi penulisan atribut dan geometri untuk seluruh bangunan
for i, ID in enumerate(OutputDict.keys()):
    cityObjectMember = etree.SubElement(CityModel, '{%s}cityObjectMember' % ns_core)
    
    Building = etree.SubElement(cityObjectMember, '{%s}Building' % ns_bldg)
    Building.set('{%s}id' % ns_gml, str(ID))
    
    FCODE = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    FCODE.set('name', 'FCODE')
    FCODEVal = etree.SubElement(FCODE, '{%s}value' % ns_gen)
    FCODEVal.text = str(attributes[i][1])
    
    NAMOBJ = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    NAMOBJ.set('name', 'NAMOBJ')
    NAMOBJVal = etree.SubElement(NAMOBJ, '{%s}value' % ns_gen)
    NAMOBJVal.text = str(attributes[i][3])
    
    REMARK = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    REMARK.set('name', 'REMARK')
    REMARKVal = etree.SubElement(REMARK, '{%s}value' % ns_gen)
    REMARKVal.text = str(attributes[i][4])
    
    AREA = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    AREA.set('name', 'AREA')
    AREAVal = etree.SubElement(AREA, '{%s}value' % ns_gen)
    AREAVal.text = str(attributes[i][7])
    
    HGROUND = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    HGROUND.set('name', 'HGROUND')
    HGROUNDVal = etree.SubElement(HGROUND, '{%s}value' % ns_gen)
    HGROUNDVal.text = str(attributes[i][8])
    
    HMAX = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    HMAX.set('name', 'HMAX')
    HMAXVal = etree.SubElement(HMAX, '{%s}value' % ns_gen)
    HMAXVal.text = str(attributes[i][9])
    
    HMIN = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    HMIN.set('name', 'HMIN')
    HMINVal = etree.SubElement(HMIN, '{%s}value' % ns_gen)
    HMINVal.text = str(attributes[i][10])
    
    UPDATED = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    UPDATED.set('name', 'UPDATED')
    UPDATEDVal = etree.SubElement(UPDATED, '{%s}value' % ns_gen)
    UPDATEDVal.text = str(attributes[i][16])
    
    NLP = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    NLP.set('name', 'NLP')
    NLPVal = etree.SubElement(NLP, '{%s}value' % ns_gen)
    NLPVal.text = str(attributes[i][17])
    
    KECAMATAN = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    KECAMATAN.set('name', 'KECAMATAN')
    KECAMATANVal = etree.SubElement(KECAMATAN, '{%s}value' % ns_gen)
    KECAMATANVal.text = str(attributes[i][18])
    
    NIBElem = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
    NIBElem.set('name', 'NIB')
    NIBVal = etree.SubElement(NIBElem, '{%s}value' % ns_gen)
    NIBValues = ''
    if len(NIB[i]) != 0:
        for code in NIB[i]:
            NIBValues = NIBValues + str(code) + ' '
        NIBVal.text = NIBValues[:-1]
        
    MeasHeight = etree.SubElement(Building, '{%s}measuredHeight' % ns_bldg)
    MeasHeight.set('uom', 'meter')
    MeasHeight.text = str(attributes[i][11])
    
    lod2Solid = etree.SubElement(Building, '{%s}lod2Solid' % ns_bldg)
    Solid = etree.SubElement(lod2Solid, '{%s}Solid' % ns_gml)
    exterior = etree.SubElement(Solid, '{%s}exterior' % ns_gml)
    CompositeSurface = etree.SubElement(exterior, '{%s}CompositeSurface' % ns_gml)
    
    Ground = '{%s}GroundSurface'
    Wall = '{%s}WallSurface'
    Roof = '{%s}RoofSurface'
    
    for semantic in OutputDict[ID].keys():
        if semantic == 'Ground':
            writing_surfaces(OutputDict[ID][semantic], Ground)
        elif semantic == 'Wall':
            writing_surfaces(OutputDict[ID][semantic], Wall)
        elif semantic == 'Roof':
            writing_surfaces(OutputDict[ID][semantic], Roof)


# In[77]:


# Menuliskan model CityGML
output_dir = '/Users/veriandi/Desktop/LOD2 Coblong (EPSG 32748) Corrected.gml'
etree.ElementTree(CityModel).write(output_dir, xml_declaration=True, encoding='utf-8', pretty_print= True)

