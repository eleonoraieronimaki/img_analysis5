from copy import deepcopy
import os
import numpy as np
import diplib as dip
import matplotlib.pyplot as plt
from skimage.io import imread
from skimage.feature import hog
import matplotlib.pyplot as plt
from natsort import natsorted
from PIL import Image

def load_dip_images(images_dir):
    """ Will only load the tif images of directory.
        Input:
            - images_dir: string containing the path
                of the directory of the image series
        Returns:
            - dip_images: list of loaded dip images
            - img_names: list of filenames
    """
    # check that directory is defined correctly
    if images_dir[-1] != "/":
        images_dir += "/"
    # load all .tif images
    dip_images = []
    img_names = []
    for filename in natsorted(os.listdir(images_dir)):
        if ".tif" in filename:
            if filename[-5] not in [str(x) for x in range(0,10)]:
                continue
            dip_images.append(dip.ImageReadTIFF(images_dir+filename))
            img_names.append(filename)
    return dip_images, img_names

def save_images(dip_images, images_dir, name_temp="", file_type="tif"):
    """ Saves the imput images
        Input:
            - dip_images: python list with the images to save
            - images_dir: string with the directory to save the images
            - name_temp: string containing the name structure 
                        to give to the series of images
            - file_type: can be string or list of file types to save image
    """

    # check that path is correctly defined
    if images_dir[-1] != "/":
        images_dir += "/"
    # create directories if needed
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
    # check name
    if name_temp != "" and name_temp[-1] != "-":
        name_temp += "-"
    # save images loop
    counter = 0
    for img in dip_images:
        if  "tif" in file_type:
            dip.ImageWriteTIFF(img,images_dir+name_temp+str(counter))
        if "jpeg" in file_type:
            # if the image is binary we need to multiply by 255
            if img.DataType() == "BIN":
                img = img * 255
            # save jpg image
            dip.ImageWriteJPEG(img,images_dir+name_temp+str(counter), 100)
            exit()
        counter += 1

def normalize_resize(dip_images:list, new_size=(323,256), normalize=True):
    new_images = []

    for i in range(len(dip_images)):
        arr = np.array(dip_images[i])
        max = 65535
        min = 0
        if normalize == True:
            arr = (((arr - min) / (max - min))*255).astype(np.uint8)
        rescaled = Image.fromarray(arr).resize(new_size)
        new_images.append(dip.Image(np.array(rescaled)))
    return new_images

def make_grayscale(dip_images: list):
    """ Converts the diplip images to grayscale
    """
    blues = []
    grays = []
    for img in dip_images:
        kuwahara = dip.Kuwahara(img, 10,10)
        array= np.array(kuwahara)
        blue_img = dip.Image(array[:,:,2])
        blues.append(blue_img)
    return blues

def invert_colors(dip_images: list):
    new_images = []
    print(len(dip_images))
    for img in dip_images:
        new_img = np.array(img) == False
        new_images.append(dip.Image(new_img))
    return new_images

def blue_area(dip_images: list,features):
    """ Converts the diplip images to unit8 and threshold them to extract the gene expression
    """
    grays = []
    blue_areas = []
    m =[]
    for img in dip_images:
        unit8 = dip.Convert(img, "UINT8")
        gauss = dip.Gauss(unit8,sigmas=[20,20])
        x = np.array(gauss)
        gray = x[:,:,0]
        grays.append(dip.Image(gray))
        thresh = dip.OtsuThreshold(gray)
        thresh = dip.Opening(thresh)
        thresh = dip.Closing(thresh)
        thresh = dip.Erosion(thresh)
        thresh = dip.Dilation(thresh)
        # thresh = dip.FillHoles(thresh)
        arr = np.array(thresh)
        inverted = 1 - arr
        inverted = ~ arr
        label = dip.Label(dip.Image(inverted), connectivity=1)
        blue_areas.append(dip.Image(inverted))
        m.append(dip.MeasurementTool.Measure(label, dip.Image(gray), features = features))
    return blue_areas, m, grays


def threshold_images(dip_images):
    """ Triangle threshold all the dip_images in the list.
        The images will be converted to grayscale if 
        not already grayscale.

        Input:
            dip_images: list of grayscale diplib images to threshold
            save: string of dir to save output images.
                Images only saved if dir is specified.
        Return:
            list of the thresholded images
    """
    images_thresh = []
    counter = 0
    for img in dip_images:
        if counter > 25:
            curr_img = dip.TriangleThreshold(img)
        else:    
            curr_img = dip.OtsuThreshold(img)
        images_thresh.append(curr_img)
        counter += 1
    return images_thresh

def apply_transformations(dip_images: list):
    """ Applies the defined transform to the dip_images
        Input:
            - dip_images: python list of diplib images
        Return:
            - out_images: python list with the transformed diplib images 
    """
    out_images = dip_images.copy()
    for i in range(len(out_images)):
        # opening to remove white pixel noise
        out_images[i] = dip.Opening(out_images[i])
        # closing to fill dark holes:
        out_images[i] = dip.Closing(out_images[i])
        # erosion to remove boundary pixels
        out_images[i] = dip.Erosion(out_images[i])
        # out_images[i] = dip.Erosion(out_images[i])
        # dilation to extend object boundary to background
        out_images[i] = dip.Dilation(out_images[i])
        # close any hole in the image
        # opening to remove white pixel noise
        # out_images[i] = dip.Opening(out_images[i])
        out_images[i] = dip.FillHoles(out_images[i])
    return out_images

def measure_elements(dip_to_measure: list, dip_grayscale: list, 
                    features):
    label_images=[]
    measurements = []
    for i in range(len(dip_to_measure)):
        curr_img = dip.Label(dip_to_measure[i], connectivity=1)

        measurements.append(dip.MeasurementTool.Measure(curr_img, 
                                dip_grayscale[i], 
                                features))
        label_images.append(curr_img)

    return label_images, measurements

def parse_features(measurements):
    """ Transforms the measurements object in numpy arrays
    """
    features = []
    for mes in measurements:
        curr_features = []
        for i in range(mes.NumberOfFeatures()):
            curr_feature = mes.Features()[i].name
            curr_feats = []

            for j in range(1, mes.NumberOfObjects()+1):
                curr_elem = mes[curr_feature][j]
                curr_feats.append(np.vstack(curr_elem))
            curr_feats = np.hstack(curr_feats)    
            curr_features.append(np.vstack(curr_feats))
        curr_features = np.vstack(curr_features).T
        features.append(curr_features)
    return features

def measurements_array(measurements, features):

    areas, perimeters, circularity, roundness, stand_dev  = [],[], [], [] , [] 
    
    test = []
    for i in range(len(measurements)):
        area, perimeter, circ, round, stds  = [], [] , [] , [] , [] 

        for j in range(1,measurements[i].NumberOfObjects()+1):

            area.append(measurements[i][features[1]][j][0]) 
            perimeter.append(measurements[i][features[0]][j][0])
            circ.append(measurements[i][features[2]][j][0])
            round.append(measurements[i][features[3]][j][0])
            stds.append(measurements[i][features[4]][j][0])

        
        test.append(area)
        idx = np.argmax(area)
        areas.append(area[idx])
        perimeters.append(perimeter[idx])
        circularity.append(circ[idx])
        roundness.append(round[idx])
        stand_dev.append(stds[idx])


    return areas, perimeters, circularity, roundness, stand_dev

def crop_images(dip_images: list, minimum, maximum, img_shape=(1300,1030), off=5):
    cropped_img = []
    for i in range(len(dip_images)):
        # max boundary pixels
        x_max_padding = int(maximum[i][0])
        y_max_padding = int(maximum[i][1])
        # min boudary pixels
        x_min_padding = int(minimum[i][0])
        y_min_padding = int(minimum[i][1])

        if x_max_padding+off > img_shape[0] or y_max_padding+off > img_shape[1] or \
            x_min_padding-off < 0 or y_min_padding-off < 0 :
            cropped_img.append(dip.Image.At(dip_images[i], 
                                slice(x_min_padding,x_max_padding), 
                                slice(y_min_padding,y_max_padding)))
        else:
            cropped_img.append(dip.Image.At(dip_images[i], 
                            slice(x_min_padding-off,x_max_padding+off), 
                            slice(y_min_padding-off,y_max_padding+off)))
    return cropped_img


def calculate_hog(dip_images: list, orientation = 8, pixels_per_cell=(16,64), rgb = True, visualize=False):

    hog_images= []
    for img in dip_images:
        _, hog_image = hog(img, orientations= orientation, 
                            pixels_per_cell=pixels_per_cell,
                            cells_per_block=(1, 1), visualize=visualize, 
                            channel_axis=-1 if rgb else None)
        hog_images.append(dip.Image(hog_image))

    return hog_images


def embryo_mask(data_orig: list, data_thresh: list, labeled=False):
    """ Filters the input images to create masks of only 
        the biggest object in the image.
    
    Params:
            - data_orig: list of original data used for some measurements
            - data_thresh: list of thresholded boolean images (masks)
                            from which to sample measurements
            - labeled:
        Returns:
            - list of iamges with only the biggest element
    """

    #transf_lab = [embryos_transf[i] > 0 for i in range(len(embryos_transf))]
    
    # choose object based on size
    measures = ['Size']
    # label image if required
    if not labeled:
        labeled_embr, measurements = measure_elements(data_thresh, 
                                                        data_orig, 
                                                        measures)
    meas_np = parse_features(measurements)
    new_images = []
    for i in range(len(labeled_embr)):
        curr_areas = meas_np[i]
        if len(curr_areas) > 1:
            max_area = curr_areas.max()
            new_img = dip.SmallObjectsRemove(data_thresh[i], int(max_area-1))
            new_images.append(new_img)
        else: 
            new_images.append(data_thresh[i])

    return new_images