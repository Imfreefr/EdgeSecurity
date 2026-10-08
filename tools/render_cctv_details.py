from PIL import Image
from prepare_cctv_v2 import ROOT

def main():
    for stem,region in [('0_te1',(0,330,580,550)),('0_te10',(1300,480,1590,780)),
                        ('4_te20',(140,80,340,245)),('7_te1',(780,175,1000,385))]:
        with Image.open(ROOT/'external/frames'/(stem+'.jpg')) as im:
            detail=im.crop(region);detail.resize((detail.width*2,detail.height*2)).save(ROOT/'review/sheets'/('detail-'+stem+'.jpg'))

if __name__=='__main__':main()
