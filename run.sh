#!/usr/bin/bash -x

# Download Town and City classification from https://commonslibrary.parliament.uk/research-briefings/cbp-8322/ 
# due to issues with cloudflare https://researchbriefings.files.parliament.uk/documents/CBP-8322/oa-classification-csv.csv
for i in archive data download output SHP
do
    if [ ! -d ${i} ]; then
        mkdir ${i}
    fi
done

if [ ! -d venv ]; then
    echo Set up python3 virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip3 install --upgrade pip
    pip3 install -r requirements.txt
else
    source venv/bin/activate
fi
export PYTHONUNBUFFERED=1

if [ ! -d jay ]; then
    git clone https://github.com/anisotropi4/jay.git
fi

echo Download Scotland mid-year estimates 2021
FILE=sape-2021.xlsx
if [ ! -s download/${FILE} ]; then
    echo here
    URL='https://www.nrscotland.gov.uk/files/statistics/population-estimates/sape-time-series'
    curl -o download/${FILE} "${URL}/${FILE}"
fi

OFILE=Mid-2021-scotland.tsv
if [ ! -s data/${OFILE} ]; then
    ./xl2tsv.py --tab "Persons" --path data --noempty download/${FILE}
    cat data/Persons.tsv | tail -n +4 > data/${OFILE}
fi

FILE=OA_DZ_IZ_2011.xlsx
if [ ! -s data/${FILE} ]; then
    URL='https://www.nrscotland.gov.uk/files//geography/2011-census/'
    curl -o data/${FILE} "${URL}/${FILE}"
fi

FILE=OA-DZ-lookup.tsv
if [ ! -s data/${FILE} ]; then
    FILEPATH=data/OA_DZ_IZ_2011.xlsx
    ./xl2tsv.py --tab "OA_DZ_IZ_2011 Lookup" --path data --noempty ${FILEPATH}
    mv "data/OA_DZ_IZ_2011 Lookup.tsv" data/${FILE}
fi

echo England and Wales mid-year estimates 2020
FILE=UR-OA-sex.tsv
if [ ! -s data/${FILE} ]; then
    URL='https://ons-dp-prod-census-publication.s3.eu-west-2.amazonaws.com/TS008_sex'
    echo Download England and Wales mid-year sex census 2021
    BASEFILE='UR-oa%2Bsex.xlsx'
    FILEPATH=download/${BASEFILE}
    curl -o ${FILEPATH} "${URL}/${BASEFILE}"
    ./xl2tsv.py --tab "Table" --path data --noempty ${FILEPATH}
    mv "data/Table.tsv" data/${FILE}
fi

FILE=OA-MS-LS.csv
if [ ! -s data/${FILE} ]; then
    URI='https://www.arcgis.com/sharing/rest/content/items/792f7ab3a99d403ca02cc9ca1cf8af02/data'
    curl -L -o data/${FILE} "${URI}"
fi

echo Download Scotland MHW OA geography
FILE=output-area-2011-mhw.zip
if [ ! -s data/${FILE} ]; then    
    URL="https://www.nrscotland.gov.uk/files/geography/"
    curl -o data/${FILE} ${URL}/${FILE}
fi


STUB=OutputArea2011_MHW
if [ ! -s data/${STUB}.shp ]; then
    (cd data; unzip ${FILE})
fi


FILE=OA-2011-boundaries-SC-BFC.gpkg
if [ ! -s data/${FILE} ]; then
    ogr2ogr -f GPKG data/${FILE} data/${STUB}.shp -t_srs EPSG:32630
fi


echo Download England and Wales MHW OA geography
FILE=OA-2021-boundaries-EW-BFC.geojson
if [ ! -s data/${FILE} ]; then
    #URI="https://services1.arcgis.com/ESMARspQHYMw9BZ9/ArcGIS/rest/services/Output_Areas_December_2011_Boundaries_EW_BFC/FeatureServer/0"
    URI="https://services1.arcgis.com/ESMARspQHYMw9BZ9/ArcGIS/rest/services/Output_Areas_Dec_2021_Boundaries_Full_Clipped_EW_BFC_2022/FeatureServer/0"
    ./fastesri.py ${URI} data/${FILE}
fi


FILE=OA-2011-boundaries-SC-BFC.gpkg
if [ ! -s data/${FILE} ]; then
    STUB=$(echo ${FILE} | sed 's/.gpkg$//')
    ogr2ogr -f GPKG data/${STUB}.gpkg data/${STUB}.geojson 
fi


FILE=OA-2021-boundaries-EW-BFC.gpkg
if [ ! -s data/${FILE} ]; then
    STUB=$(echo ${FILE} | sed 's/.gpkg$//')
    ogr2ogr -f GPKG data/${STUB}.gpkg data/${STUB}.geojson -t_srs EPSG:32630
fi

if [ ! -s geography.gpkg ]; then
    ./geography.py
fi

FILE='OA2011_OA2021_LocalAuthorityDistrict2022_EW.csv'
if [ ! -s data/${FILE} ]; then
    URI=https://services1.arcgis.com/ESMARspQHYMw9BZ9/ArcGIS/rest/services/Output_Areas_2011_to_Output_Areas_2021_to_Local_Authority_District_2022_Loo_2022/FeatureServer/0
    ./fastesri.py --csv ${URI} data/${FILE}
fi

FILESTUB='geography'
if [ ! -s ${FILESTUB}-simple.gpkg ]; then
    (cd jay; ./simplify.sh ../${FILESTUB}.gpkg)
    ln jay/output/${FILESTUB}-simple.gpkg ${FILESTUB}-simple.gpkg
fi

FILE='hex30-OA.gpkg'
if [ ! -s ${FILE} ]; then
    ./hex30.py
fi
