/*
  ==============================================================================

    crc7.h
    Created: 20 Dec 2016 3:00:31pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#ifndef CRC7_H_INCLUDED
#define CRC7_H_INCLUDED

#include "../JuceLibraryCode/JuceHeader.h"

class Crc7
{
public:
	//==============================================================================

	Crc7();
	~Crc7();

	unsigned int GetSize(void);
	void AddPage(unsigned short *AUDIO_DATA,int PAGE_ADDR);
	void AddStartMessage(int SAMPLE_NO);
	void AddStopMessage(void);
	//void addCrc(void);
	//unsigned int ReadFile(MemoryBlock *DATA);

	//unsigned int getDeviceID(void);
	//unsigned int getNoOfPackages(void);

	MidiMessage GetMessage(unsigned int INDEX);


private:
	//==============================================================================

	Array<MidiMessage> SysExStrings;
	unsigned char DATA[64];
	unsigned char SIZE;
	unsigned char INDEX;

	unsigned char CalcCrc(unsigned char u08CRC, unsigned char u08DATA);




protected:


};



#endif  // CRC7_H_INCLUDED

