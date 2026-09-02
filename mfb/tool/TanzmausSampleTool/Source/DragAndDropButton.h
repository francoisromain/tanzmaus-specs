/*
  ==============================================================================

    DragAndDropButton.h
    Created: 16 Dec 2016 1:14:17pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#ifndef DRAGANDDROPBUTTON_H_INCLUDED
#define DRAGANDDROPBUTTON_H_INCLUDED

#include "../JuceLibraryCode/JuceHeader.h"
#include "pBar.h"

//==============================================================================
/*
*/
class DragAndDropButton : public TextButton,
							 public FileDragAndDropTarget
{
public:
	DragAndDropButton();
    ~DragAndDropButton();

    //void paintProgress (Graphics&);
   // void resized() override;
	void filesDropped(const StringArray &  	files, int  	x, int  	y) override;
	virtual bool isInterestedInFileDrag(const StringArray &  	files) override;
	String getFileName(void);
	void SetProgressBarPointer(Test *POINTER);
	void SetDataFilePointer(File *POINTER);
	void SetDropable(void);
	void ClearDropable(void);
    void SetName(const String& NEW_NAME);
	

private:
	JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(DragAndDropButton)
	String FILENAME;
	Test *progBar;
	int ACTIV;
	int STATE;
	
	
};


#endif  // DRAGANDDROPBUTTON_H_INCLUDED
