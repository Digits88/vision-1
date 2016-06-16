#!/usr/bin/env python2
__author__ = 'tesfa'
import os
import sys
import subprocess
import rospy
import cv2
from std_msgs.msg import String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
import message_filters
from std_srvs.srv import Empty
from cmt_tracker_msgs.msg import Trackers,Tracker, Objects
from cmt_tracker_msgs.srv import TrackerNames,MergeNames
import itertools
'''
Description: This is checks for the if cmt_tracker is overlapping with cmt instances and focuses the libraries to the locations.

Thus validates tracker to filter out values in the output of the tracker.
    - This before set's to avoid setting names or evaluating overlap before name is changed
    - This happens to avoid setting trackers for false positives in the tracker.

    Later: (Customization of the optical flow points into area that is being tracker bad. )
    - This also uses to set the area of the tracker to reset the tracker if it diverges a lot.
    - If an cmt_tracker location has stayed in one location for quite a while and thus indication that it's may not be a face it's tracking.

Another is to destroy after a while if the tracker is going to garabage levels.

'''
class face_reinforcer:
    def __init__(self):
        rospy.init_node('face_reinforcer', anonymous=True)
        self.filtered_face_locations = rospy.get_param('filtered_face_locations')
        self.cmt_sub = message_filters.Subscriber('temporary_trackers',Trackers)
        self.tracker_locations_pub = rospy.Publisher("tracking_locations", Trackers, queue_size=5)
        self.cmt_sub_ = message_filters.Subscriber('tracker_results', Trackers)
        self.face_sub = message_filters.Subscriber(self.filtered_face_locations, Objects)
        self.faces_cmt_overlap = {}
        self.srvs = rospy.Service('can_add_tracker', Empty, self.can_update)

        ts = message_filters.ApproximateTimeSynchronizer([self.cmt_sub,self.face_sub,self.cmt_sub_], 1,0.2)
        ts.registerCallback(self.callback)

        self.update = True
    def can_update(self, req):
        self.update = True
        return []

    def callback(self, cmt, face,temp):

        ttp = cmt
        for val in temp.tracker_results:
            ttp.tracker_results.append(val)

        not_overlapped, overlaped_faces = self.returnOverlapping(face,ttp)

        if len(not_overlapped) > 0 and self.update:
            self.tracker_locations_pub.publish(self.convert(not_overlapped))
            rospy.set_param('tracker_updated', 2)
            rospy.set_param("being_initialized_stop", 1)
            self.update = False

        for face, cmt in overlaped_faces:

            self.faces_cmt_overlap[cmt.tracker_name.data] = self.faces_cmt_overlap.get(cmt.tracker_name.data, 0) + 2
            if (self.faces_cmt_overlap[cmt.tracker_name.data] > 2):
                try:
                    self.upt = rospy.ServiceProxy('reinforce',TrackerNames)
                    indication = self.upt(names=cmt.tracker_name.data, index=500)
                    if not indication:
                        #TODO handle the error if the service is not available.
                        pass
                except rospy.ServiceException, e:
                    self.logger.error("Service call failed: %s" % e)

        # TODO if the cmt name has disappeared then remove it from the self.faces_cmt_overlap.get Via Subscriber to Face_events
        self.cmt_merge = {}
        merge_to=[]
        merge_from=[]
        for a, b in itertools.combinations(ttp.tracker_results, 2):
            SA = a.object.object.height * a.object.object.width
            SB = b.object.object.height * b.object.object.width
            SI = max(0, (
                max(a.object.object.x_offset + a.object.object.width, b.object.object.x_offset + b.object.object.width) - min(
                    a.object.object.x_offset, b.object.object.x_offset))
                         * max(0, max(a.object.object.y_offset, b.object.object.y_offset) - min(
                    a.object.object.y_offset - a.object.object.height, b.object.object.y_offset - b.object.object.height)))
            SU = SA + SB - SI
            overlap_area_ = SI / SU

            overlap_ = overlap_area_ > 0
            if (overlap_):
                #TODO Choose which to merge too later information to which it's closer too.
                self.cmt_merge[a.tracker_name.data] = self.cmt_merge.get(a.tracker_name.data,b.tracker_name.data)
                merge_to.append(a.tracker_name.data)
                merge_from.append(b.tracker_name.data)

        #TODO for now just delete the elements then latter put a mark on the merged elements and update if there is overlappings with the track.
        try:
            self.mrg = rospy.ServiceProxy('merge',MergeNames)
            indic =self.mrg(merge_to=merge_to, merge_from=merge_from)
            if not indic:
                pass
        except rospy.ServiceException, e:
            print("Service call failed: %s" % e)

        # Now pass to the merger.



    def returnOverlapping(self, face, cmt):
        not_covered_faces = []
        overlaped_faces = []
        for j in face.objects:
            overlap = False
            SA = j.object.height * j.object.width
            for i in cmt.tracker_results:
                SB = i.object.object.height * i.object.object.width
                SI = max(0, (
                max(j.object.x_offset + j.object.width, i.object.object.x_offset + i.object.object.width) - min(
                    j.object.x_offset, i.object.object.x_offset))
                         * max(0, max(j.object.y_offset, i.object.object.y_offset) - min(
                    j.object.y_offset - j.object.height, i.object.object.y_offset - i.object.object.height)))
                SU = SA + SB - SI
                overlap_area = SI / SU
                overlap = overlap_area > 0
                if (overlap):
                    list = [j, i]
                    overlaped_faces.append(list)
                    break
            if not overlap:
                not_covered_faces.append(j)
        return not_covered_faces, overlaped_faces

    def convert(self, face_locs):
        message = Trackers()
        for i in face_locs:
            messg = Tracker()
            messg.object = i
            message.tracker_results.append(messg)
        message.header.stamp = rospy.Time.now()
        return message

if __name__ == '__main__':
    ic = face_reinforcer()
    try:
        rospy.spin()
    except KeyboardInterrupt:
        pass