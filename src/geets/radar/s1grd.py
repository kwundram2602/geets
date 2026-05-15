import ee
import math as Math

# https://www.linkedin.com/pulse/sentinel-1-sar-data-pre-processing-google-earth-engine-pradhan-s6roc/
def load_s1grd(start_date, end_date):
    s1grd = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterDate(start_date, end_date)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )
    return s1grd


def toNatural(img):
    return ee.Image(10.0).pow(img.select(0).divide(10.0))


def toDB(img):
    return ee.Image(img).log10().multiply(10.0)


def terrainCorrection(image, srtm):
    imgGeom = image.geometry()
    srtm = srtm.clip(imgGeom)
    sigma0Pow = ee.Image.constant(10).pow(image.divide(10.0))
    theta_i = image.select("angle")
    phi_i = (
        ee.Terrain.aspect(theta_i)
        .reduceRegion(ee.Reducer.mean(), theta_i.get("system:footprint"), 1000)
        .get("aspect")
    )
    alpha_s = ee.Terrain.slope(srtm).select("slope")
    phi_s = ee.Terrain.aspect(srtm).select("aspect")
    phi_r = ee.Image.constant(phi_i).subtract(phi_s)
    phi_rRad = phi_r.multiply(Math.pi / 180)
    alpha_sRad = alpha_s.multiply(Math.pi / 180)
    theta_iRad = theta_i.multiply(Math.pi / 180)
    ninetyRad = ee.Image.constant(90).multiply(Math.pi / 180)
    alpha_r = (alpha_sRad.tan().multiply(phi_rRad.cos())).atan()
    alpha_az = (alpha_sRad.tan().multiply(phi_rRad.sin())).atan()
    theta_lia = (alpha_az.cos().multiply((theta_iRad.subtract(alpha_r)).cos())).acos()
    theta_liaDeg = theta_lia.multiply(180 / Math.pi)
    gamma0 = sigma0Pow.divide(theta_iRad.cos())
    gamma0dB = ee.Image.constant(10).multiply(gamma0.log10())
    ratio_1 = gamma0dB.select("VV").subtract(gamma0dB.select("VH"))
    nominator = (ninetyRad.subtract(theta_iRad).add(alpha_r)).tan()
    denominator = (ninetyRad.subtract(theta_iRad)).tan()
    volModel = (nominator.divide(denominator)).abs()
    gamma0_Volume = gamma0.divide(volModel)
    gamma0_VolumeDB = ee.Image.constant(10).multiply(gamma0_Volume.log10())
    alpha_rDeg = alpha_r.multiply(180 / Math.pi)
    layover = alpha_rDeg.lt(theta_i)
    shadow = theta_liaDeg.lt(85)
    ratio = gamma0_VolumeDB.select("VV").subtract(gamma0_VolumeDB.select("VH"))
    output = (
        gamma0_VolumeDB.addBands(ratio)
        .addBands(alpha_r)
        .addBands(phi_s)
        .addBands(theta_iRad)
        .addBands(layover)
        .addBands(shadow)
        .addBands(gamma0dB)
        .addBands(ratio_1)
    )
    return image.addBands(output.select(["VV", "VH"], ["VV", "VH"]), None, True)
