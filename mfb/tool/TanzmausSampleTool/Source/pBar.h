/*
  ==============================================================================

    pBar.h
    Created: 6 Jan 2017 2:23:39pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#ifndef PBAR_H_INCLUDED
#define PBAR_H_INCLUDED


#include "../JuceLibraryCode/JuceHeader.h"

//==============================================================================
/*
*/
class Test    : public Component
{
public:
    Test();
    ~Test();

    void paint (Graphics&) override;
    void resized() override;
	void progress(float prog);
	void ChangeBarText(String TEXT);

private:
	JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(Test)
		float progValue;
	String BAR_TEXT;
};


#endif  // PBAR_H_INCLUDED
