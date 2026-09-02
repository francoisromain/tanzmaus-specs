/*
  ==============================================================================

    crc7.cpp
    Created: 20 Dec 2016 3:00:31pm
    Author:  y

  ==============================================================================
*/

#include "crc7.h"

Crc7::Crc7(){

}

Crc7::~Crc7(){

}

unsigned char Crc7::CalcCrc(unsigned char u08CRC, unsigned char u08DATA){
	u08DATA ^= u08CRC << 1;

	if (u08DATA & 0x80)
		u08DATA ^= 9;

	u08CRC = u08DATA ^ (u08CRC & 0x78) ^ (u08CRC << 4) ^ ((u08CRC >> 3) & 15);

	return u08CRC & 0x7f;
}

void Crc7::AddStartMessage(int SAMPLE_NO) {
	unsigned char TEMP_BUFFER[7];
	const unsigned char SYSEX_START_PATTERN[6] = { 0x00, 0x21, 0x0b, 0x04, 0x00, 0x06 };
	int i;

	for (i = 0; i < 6; i++) {
		TEMP_BUFFER[i] = SYSEX_START_PATTERN[i];
	}
	TEMP_BUFFER[6] = SAMPLE_NO;
	SysExStrings.add(MidiMessage::createSysExMessage((const void*)TEMP_BUFFER, 7));
}

void Crc7::AddStopMessage(void) {
	unsigned char TEMP_BUFFER[58];
	const unsigned char SYSEX_START_PATTERN[6] = { 0x00, 0x21, 0x0b, 0x04, 0x00, 0x07 };
	int i;

	for (i = 0; i < 6; i++) {
		TEMP_BUFFER[i] = SYSEX_START_PATTERN[i];
	}
	
	SysExStrings.add(MidiMessage::createSysExMessage((const void*)TEMP_BUFFER, 6));
}

void Crc7::AddPage(unsigned short *AUDIO_DATA, int PAGE_ADDR){
	int PAGE_COUNTER = 0,i,j,SAMPLE_INDEX=0;
	unsigned char SUB_PACKET_COUNTER = 0;
	unsigned char TEMP_BUFFER[58];
	unsigned char LOW_BYTE, HIGH_BYTE;
	unsigned char CHECKSUM=0;
	const unsigned char SYSEX_START_PATTERN[6] = {0x00, 0x21, 0x0b, 0x04, 0x00, 0x05 };

	for (j = 0; j < 11; j++){
		//start string
		for (i = 0; i < 6; i++){
			TEMP_BUFFER[i] = SYSEX_START_PATTERN[i];
		}
		CHECKSUM = 0;
		//PAGE ADDR
		TEMP_BUFFER[6] = (unsigned char)(PAGE_ADDR & 0x7f);			//LOW
		TEMP_BUFFER[7] = (unsigned char)((PAGE_ADDR >> 7) & 0x7f);	//HIGH

		//sub packet no
		TEMP_BUFFER[8] = SUB_PACKET_COUNTER;

		for (i = 0; i < 48; i++){
			if ((i % 2) == 0)TEMP_BUFFER[i+9] = (unsigned char)(AUDIO_DATA[SAMPLE_INDEX] & 0x7f); 
			else {
				TEMP_BUFFER[i + 9] = (unsigned char)((AUDIO_DATA[SAMPLE_INDEX] >> 7) & 0x7f);
				SAMPLE_INDEX++;
			}
		}
		for (i = 0; i < 57; i++){
			CHECKSUM = CalcCrc(CHECKSUM, TEMP_BUFFER[i]);
		}
		//TEMP_BUFFER[57] = SAMPLE_NO;
		TEMP_BUFFER[57] = CHECKSUM;
		SysExStrings.add(MidiMessage::createSysExMessage((const void*)TEMP_BUFFER, 58));
		SUB_PACKET_COUNTER++;
	}
}

MidiMessage Crc7::GetMessage(unsigned int INDEX){
	return SysExStrings[INDEX];
}

unsigned int Crc7::GetSize(void){
	return SysExStrings.size();
}