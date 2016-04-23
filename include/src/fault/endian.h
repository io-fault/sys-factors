#define BYTESWAP2(CP) do { \
	register unsigned char c; \
	c=CP[1];CP[1]=CP[0];CP[0]=c; \
} while(0)

#define BYTESWAP3(CP) do { \
	register unsigned char c; \
	c=CP[2];CP[2]=CP[0];CP[0]=c; \
} while(0)

#define BYTESWAP4(P) do { \
	register unsigned char c; \
	c=P[3];P[3]=P[0];P[0]=c; \
	c=P[2];P[2]=P[1];P[1]=c; \
} while(0)

#define BYTESWAP5(P) do { \
	register unsigned char c; \
	c=P[4];P[4]=P[0];P[0]=c; \
	c=P[3];P[3]=P[1];P[1]=c; \
} while(0)

#define BYTESWAP8(P) do { \
	register unsigned char c; \
	c=P[7];P[7]=P[0];P[0]=c; \
	c=P[6];P[6]=P[1];P[1]=c; \
	c=P[5];P[5]=P[2];P[2]=c; \
	c=P[4];P[4]=P[3];P[3]=c; \
} while(0)

#define BYTESWAP10(P) do { \
	register unsigned char c; \
	c=P[9];P[9]=P[0];P[0]=c; \
	c=P[8];P[8]=P[1];P[1]=c; \
	c=P[7];P[7]=P[2];P[2]=c; \
	c=P[6];P[6]=P[3];P[3]=c; \
	c=P[4];P[5]=P[4];P[4]=c; \
} while(0)

#define BYTESWAP12(P) do { \
	register unsigned char c; \
	c=P[11];P[11]=P[0];P[0]=c; \
	c=P[10];P[10]=P[1];P[1]=c; \
	c=P[ 9];P[ 9]=P[2];P[2]=c; \
	c=P[ 8];P[ 8]=P[3];P[3]=c; \
	c=P[ 7];P[ 7]=P[4];P[4]=c; \
	c=P[ 6];P[ 6]=P[5];P[5]=c; \
} while(0)

#define BYTESWAP16(P) do { \
	register unsigned char c; \
	c=P[15];P[15]=P[0];P[0]=c; \
	c=P[14];P[14]=P[1];P[1]=c; \
	c=P[13];P[13]=P[2];P[2]=c; \
	c=P[12];P[12]=P[3];P[3]=c; \
	c=P[11];P[11]=P[4];P[4]=c; \
	c=P[10];P[10]=P[5];P[5]=c; \
	c=P[ 9];P[ 9]=P[6];P[6]=c; \
	c=P[ 8];P[ 8]=P[7];P[7]=c; \
} while(0)

#define BYTESWAP24(P) do { \
	register unsigned char c; \
	c=P[23];P[23]=P[0 ];P[0 ]=c; \
	c=P[22];P[22]=P[1 ];P[1 ]=c; \
	c=P[21];P[21]=P[2 ];P[2 ]=c; \
	c=P[20];P[20]=P[3 ];P[3 ]=c; \
	c=P[19];P[19]=P[4 ];P[4 ]=c; \
	c=P[18];P[18]=P[5 ];P[5 ]=c; \
	c=P[17];P[17]=P[6 ];P[6 ]=c; \
	c=P[16];P[16]=P[7 ];P[7 ]=c; \
	c=P[15];P[15]=P[8 ];P[8 ]=c; \
	c=P[14];P[14]=P[9 ];P[9 ]=c; \
	c=P[13];P[13]=P[10];P[10]=c; \
	c=P[12];P[12]=P[11];P[11]=c; \
} while(0)

#define BYTESWAP32(P) do { \
	register unsigned char c; \
	c=P[31];P[31]=P[0 ];P[0 ]=c; \
	c=P[30];P[30]=P[1 ];P[1 ]=c; \
	c=P[29];P[29]=P[2 ];P[2 ]=c; \
	c=P[28];P[28]=P[3 ];P[3 ]=c; \
	c=P[27];P[27]=P[4 ];P[4 ]=c; \
	c=P[26];P[26]=P[5 ];P[5 ]=c; \
	c=P[25];P[25]=P[6 ];P[6 ]=c; \
	c=P[24];P[24]=P[7 ];P[7 ]=c; \
	c=P[23];P[23]=P[8 ];P[8 ]=c; \
	c=P[22];P[22]=P[9 ];P[9 ]=c; \
	c=P[21];P[21]=P[10];P[10]=c; \
	c=P[20];P[20]=P[11];P[11]=c; \
	c=P[19];P[19]=P[12];P[12]=c; \
	c=P[18];P[18]=P[13];P[13]=c; \
	c=P[17];P[17]=P[14];P[14]=c; \
	c=P[16];P[16]=P[15];P[15]=c; \
} while(0)
