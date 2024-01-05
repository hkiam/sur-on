    """
    Common 7 Segment
          - A - 
        F       B
        | - G - |
        E       C
          - D -      DP
    """   
    """
    Segments:
    F0400 - F0427

    Address     Segment                 Bit/Symbol
                            07  06  05  04  03  02  01  00          
    F0400       SEG00:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment 1 + A(FGE)
    F0401       SEG01:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment A(ABCD)
    F0402       SEG02:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment B(FGE) + Percent Symbol
    F0403       SEG03:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment B(ABCD)
    F0404       SEG04:      NC  NC  NC  NC  NC  NC  NC  NC          <- Battery Level 4 5 + Flash Symbol
    F0405       SEG05:      NC  NC  NC  NC  NC  08  07  06          <- Battery Level 1 2 3
    F0406       SEG06:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment C(ABCD)
    F0407       SEG07:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment C(EGF)  V Symbol
    F0408       SEG08:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment B(ABCD)
    F0409       SEG09:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment B(EGF) + Dot

    F040A       SEG10:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment A(ABCD)
    F040B       SEG11:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment A(EGF)
    F040C       SEG12:      NC  NC  NC  NC  NC  11  10  09          <- Line Bottom, Total + Trip Symbol
    F040D       SEG13:      NC  NC  NC  NC  NC  NC  NC  NC          <- Distance Segment F(ABCD)
    F040E       SEG14:      NC  NC  NC  NC  NC  NC  NC  NC          <- Distance Segment F(EGF) + Dot
    F040F       SEG15:      NC  NC  NC  NC  NC  NC  NC  NC          <- Distance Segment E(ABCD)
    F0410       SEG16:      NC  NC  NC  NC  NC  14  13  12          <- Distance Segment E(EGF)
    F0411       SEG17:      NC  NC  NC  NC  18  17  16  15          <- Distance Segment D(ABCD)
    F0412       SEG18:      NC  NC  NC  NC  NC  21  20  19          <- Distance Segment D(EGF)
    F0413       SEG19:      NC  NC  NC  NC  NC  NC  NC  NC

    F0414       SEG20:      NC  NC  NC  NC  25  24  23  22          <- Distance Segment C(ABCD)
    F0415       SEG21:      NC  NC  NC  NC  NC  NC  NC  NC
    F0416       SEG22:      NC  NC  NC  NC  NC  28  27  26          <- Distance Segment C(EGF)
    F0417       SEG23:      NC  NC  NC  NC  32  31  30  29          <- Distance Segment B(ABCD)
    F0418       SEG24:      NC  NC  NC  NC  NC  35  34  33          <- Distance Segment B(EGF)
    F0419       SEG25:      NC  NC  NC  NC  39  38  37  36          <- Distance Segment A(ABCD)
    F041A       SEG26:      NC  NC  NC  NC  NC  42  41  40          <- Distance Segment A(EGF)
    F041B       SEG27:      NC  NC  NC  NC  NC  NC  NC  NC          <- Gear Segment B(ABCD)
    F041C       SEG28:      NC  NC  NC  NC  NC  NC  NC  NC
    F041D       SEG29:      NC  NC  NC  NC  NC  NC  NC  NC

    F041E       SEG30:      NC  NC  NC  NC  NC  NC  NC  NC
    F041F       SEG31:      NC  NC  NC  NC  NC  NC  NC  NC          <- Gear Segment B(EGF) + Dot Symbol
    F0420       SEG32:      NC  NC  NC  NC  NC  NC  NC  NC          <- Gear Segment A(ABCD)
    F0421       SEG33:      NC  NC  NC  NC  02  NC  NC  NC          <- Gear Segment A(EGF) + MPH Symbol
    F0422       SEG34:      NC  NC  NC  NC  NC  45  44  43          <- Surron Label (1) + Gear Symbol (4) + Max Symbol (2)
    F0423       SEG35:      NC  NC  NC  NC  49  48  47  46          <- Speed Segment B(ABCD)
    F0424       SEG36:      NC  NC  NC  NC  53  52  51  50          <- Speed Segment B(EGF) + KM/H Symbol
    F0425       SEG37:      NC  NC  NC  NC  57  56  55  54          <- Speed Segment A(ABCD)
    F0426       SEG38:      NC  NC  NC  NC  61  60  59  58          <- Speed Segment 1 + A(EGF)

    ```asciiart
    Common 7 Segment
        - A - 
        F       B
        | - G - |
        E       C
        - D -      DP
    ```

    ```asciiart
    SPEED SEGMENT (S):
    SYM 1     B       C
            -       -
        |   |   |   |   |
            -       -
        |   |   |   |   |
            -       -
    ```

    ```asciiart
    DISTANCE SEGMENT (D):
    SYM  A       B       C       D       E          F
        -       -       -       -       -          -  
    |   |   |   |   |   |   |   |   |   |      |   |
        -       -       -       -       -          -  
    |   |   |   |   |   |   |   |   |   |      |   |
        -       -       -       -       -     #    -  
    ```
